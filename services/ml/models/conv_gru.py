"""Skip-ConvGRU cell — adapted from U-RNN (MIT License).

Original: Cao et al., "U-RNN: An Urban Pluvial Flood Prediction Model Based
on Recurrent Neural Network", Journal of Hydrology, 2025.
Source: https://github.com/holmescao/U-RNN (MIT License)

This file is a derivative work under the MIT License.
Copyright (c) 2024 Chenyu Cao. Original MIT License preserved.

Modifications for Urban Flood Nowcasting System:
1. Removed .cuda() hardcoding — device-agnostic via parameter
2. Simplified API for our pipeline integration
3. Added type hints and documentation
4. Removed gradient checkpointing for clarity (can be re-added)
"""

import torch
import torch.nn as nn


class SkipConvGRUCell(nn.Module):
    """Convolutional GRU cell with optional skip connections from encoder state.

    Two modes:
    - encoder: Standard ConvGRU — gates = f(x, h_{t-1})
    - decoder: Skip-ConvGRU — gates = f(x, encoder_state, decoder_state)
      The encoder state is a FIXED input (skip connection) that influences
      gates and candidate but is NOT updated by the GRU.

    Adapted from U-RNN ConvRNN.py (MIT License, Cao et al. 2025).

    Args:
        input_channels: Channels of the incoming feature map x_t
        num_features: Number of hidden state channels F
        kernel_size: Kernel size for convolutional gates (default 5)
        mode: 'encoder' or 'decoder' — controls skip-connection variant
    """

    def __init__(
        self,
        input_channels: int,
        num_features: int,
        kernel_size: int = 5,
        mode: str = "encoder",
    ):
        super().__init__()
        self.input_channels = input_channels
        self.num_features = num_features
        self.kernel_size = kernel_size
        self.padding = (kernel_size - 1) // 2
        self.mode = mode

        if mode == "encoder":
            # Standard: gates take cat(x_t, h_{t-1})
            gate_input_ch = input_channels + num_features
        elif mode == "decoder":
            # Skip: gates take cat(x_t, encoder_state, decoder_state)
            gate_input_ch = input_channels + 2 * num_features
        else:
            raise ValueError(f"mode must be 'encoder' or 'decoder', got '{mode}'")

        # Gate convolution: produces update gate z and reset gate r
        self.gate_conv = nn.Sequential(
            nn.Conv2d(gate_input_ch, 2 * num_features, kernel_size, 1, self.padding),
            nn.GroupNorm(max(1, 2 * num_features // 32), 2 * num_features),
        )

        # Candidate convolution: produces candidate hidden state
        self.candidate_conv = nn.Sequential(
            nn.Conv2d(gate_input_ch, num_features, kernel_size, 1, self.padding),
            nn.GroupNorm(max(1, num_features // 32), num_features),
        )

    def forward(
        self,
        x: torch.Tensor,
        hidden: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Forward pass for one time step.

        Args:
            x: Input tensor (B, input_channels, H, W)
            hidden: Previous hidden state
                - encoder: (B, F, H, W) or None
                - decoder: (B, 2*F, H, W) = cat(encoder_state, decoder_state)

        Returns:
            Updated hidden state (B, F, H, W)
        """
        device = x.device
        B, _, H, W = x.shape

        if hidden is None:
            hidden = torch.zeros(B, self.num_features, H, W, device=device)

        # Concatenate input with hidden state for gate computation
        combined = torch.cat([x, hidden], dim=1)

        # Compute gates
        gates = self.gate_conv(combined)
        z_gate, r_gate = torch.split(gates, self.num_features, dim=1)
        z = torch.sigmoid(z_gate)  # Update gate
        r = torch.sigmoid(r_gate)  # Reset gate

        # Compute candidate
        if self.mode == "encoder":
            # Standard: candidate uses reset-gated hidden state
            candidate_input = torch.cat([x, r * hidden], dim=1)
        else:
            # Decoder skip: split hidden into encoder_state and decoder_state
            enc_state, dec_state = torch.split(hidden, self.num_features, dim=1)
            # Reset gate only applies to decoder state; encoder state passes through
            candidate_input = torch.cat([x, enc_state, r * dec_state], dim=1)

        candidate = torch.tanh(self.candidate_conv(candidate_input))

        # Update hidden state
        if self.mode == "encoder":
            h_new = (1 - z) * hidden + z * candidate
        else:
            # Only update the decoder component
            h_new = (1 - z) * dec_state + z * candidate

        return h_new  # (B, F, H, W)


class ConvGRUEncoder(nn.Module):
    """Multi-scale ConvGRU encoder with 3 spatial scales.

    Processes spatiotemporal input through progressively coarser scales:
    - Stage 1: Full resolution
    - Stage 2: Half resolution (after AvgPool2d(2))
    - Stage 3: Quarter resolution (after AvgPool2d(2))

    Adapted from U-RNN encoder.py (MIT License).
    """

    def __init__(
        self,
        input_channels: int = 3,
        features: list[int] | None = None,
        kernel_size: int = 5,
    ):
        super().__init__()
        if features is None:
            features = [32, 64, 128]

        self.stages = nn.ModuleList()
        self.rnns = nn.ModuleList()

        in_ch = input_channels
        for i, f in enumerate(features):
            # Convolutional projection (with optional pooling)
            layers = [nn.Conv2d(in_ch, f, 3, 1, 1), nn.GroupNorm(max(1, f // 8), f), nn.SiLU()]
            if i > 0:
                layers.insert(0, nn.AvgPool2d(2))
            self.stages.append(nn.Sequential(*layers))

            self.rnns.append(SkipConvGRUCell(f, f, kernel_size, mode="encoder"))
            in_ch = f

        self.num_stages = len(features)
        self.features = features

    def forward(
        self,
        x_seq: torch.Tensor,
        states: list[torch.Tensor | None] | None = None,
    ) -> list[torch.Tensor]:
        """Encode a sequence through all stages.

        Args:
            x_seq: (T, B, C, H, W) input sequence
            states: Previous hidden states per stage, or None

        Returns:
            List of updated hidden states [stage1, stage2, stage3]
        """
        T = x_seq.shape[0]
        if states is None:
            states = [None] * self.num_stages

        new_states = []
        current_input = x_seq

        for s in range(self.num_stages):
            # Apply conv projection to each timestep
            projected = []
            for t in range(T):
                projected.append(self.stages[s](current_input[t]))
            projected = torch.stack(projected)  # (T, B, F, H', W')

            # Run ConvGRU across time
            h = states[s]
            for t in range(T):
                h = self.rnns[s](projected[t], h)

            new_states.append(h)
            current_input = projected  # Feed to next stage

        return new_states


class ConvGRUDecoder(nn.Module):
    """Multi-scale Skip-ConvGRU decoder with encoder skip connections.

    Processes from coarsest to finest scale, using encoder states as
    skip connections at each scale.

    Adapted from U-RNN decoder.py (MIT License).
    """

    def __init__(
        self,
        features: list[int] | None = None,
        kernel_size: int = 5,
    ):
        super().__init__()
        if features is None:
            features = [32, 64, 128]

        self.num_stages = len(features)
        self.features = features

        # Decoder stages process from coarse to fine
        self.rnns = nn.ModuleList()
        self.upsample = nn.ModuleList()

        for i in range(self.num_stages):
            self.rnns.append(
                SkipConvGRUCell(features[i], features[i], kernel_size, mode="decoder")
            )
            if i < self.num_stages - 1:
                # Upsample from coarse to fine
                self.upsample.append(
                    nn.ConvTranspose2d(features[i + 1], features[i], 4, 2, 1)
                )

    def forward(
        self,
        encoder_states: list[torch.Tensor],
        decoder_states: list[torch.Tensor | None] | None = None,
    ) -> list[torch.Tensor]:
        """Decode using encoder skip connections.

        Args:
            encoder_states: [stage1_enc, stage2_enc, stage3_enc]
            decoder_states: Previous decoder hidden states, or None

        Returns:
            Updated decoder states [stage1, stage2, stage3]
        """
        if decoder_states is None:
            decoder_states = [None] * self.num_stages

        new_states = []

        # Process from coarsest (stage N-1) to finest (stage 0)
        x = None
        for s in reversed(range(self.num_stages)):
            enc_state = encoder_states[s]

            if x is None:
                # Coarsest stage: no input from previous decoder stage
                x = torch.zeros_like(enc_state)
            else:
                # Upsample from coarser decoder output
                x = self.upsample[s](x)
                # Handle spatial size mismatch
                if x.shape[2:] != enc_state.shape[2:]:
                    x = nn.functional.interpolate(
                        x, size=enc_state.shape[2:], mode="bilinear", align_corners=False
                    )

            # Build skip-connected hidden state: cat(encoder_state, decoder_state)
            dec_state = decoder_states[s]
            if dec_state is None:
                dec_state = torch.zeros_like(enc_state)
            combined_hidden = torch.cat([enc_state, dec_state], dim=1)

            # Run skip-ConvGRU
            h_new = self.rnns[s](x, combined_hidden)
            new_states.insert(0, h_new)
            x = h_new

        return new_states


# Aliases for architecture naming
SkipConvGRUEncoder = ConvGRUEncoder
SkipConvGRUDecoder = ConvGRUDecoder

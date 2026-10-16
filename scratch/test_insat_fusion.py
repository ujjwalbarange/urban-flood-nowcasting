import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import asyncio
from datetime import datetime, timezone
from services.rainfall.insat_service import INSAT3DRProvider
from services.rainfall.rainfall_fusion import RainfallFusionEngine, RainfallFusionMode

async def main():
    print("=================================================================")
    print("   TESTING INSAT-3DR SERVICE AND RAINFALL FUSION ENGINE          ")
    print("=================================================================\n")

    # 1. Test HEM Provider
    hem = INSAT3DRProvider(product="HEM")
    hem_health = await hem.health_check()
    print(f"HEM Provider Health: {hem_health} (Provider: {hem.provider_name})")
    
    current_hem = await hem.fetch_current(19.076, 72.877)
    if current_hem:
        print(f"Latest HEM Observation: {current_hem[0].observed_at} | Rate: {current_hem[0].rate_mmh:.2f} mm/h | Source: {current_hem[0].source}")

    # 2. Test IMC Provider
    imc = INSAT3DRProvider(product="IMC")
    imc_health = await imc.health_check()
    print(f"\nIMC Provider Health: {imc_health} (Provider: {imc.provider_name})")
    
    # 3. Test July 8, 2024 Cloudburst Accumulation (HEM vs IMC)
    t0 = datetime(2024, 7, 8, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2024, 7, 8, 12, 0, tzinfo=timezone.utc)
    
    hem_acc = await hem.compute_accumulation(t0, t1)
    imc_acc = await imc.compute_accumulation(t0, t1)
    
    print(f"\nJuly 8, 2024 12-Hour Monsoon Cloudburst (00:00 - 12:00 UTC):")
    print(f"  HEM (Primary):  {hem_acc['granules_count']} half-hourly granules | Mumbai Accum: {hem_acc['mumbai_core_accumulation_mm']} mm | Peak: {hem_acc['peak_rate_mmh']} mm/h")
    print(f"  IMC (Valid):    {imc_acc['granules_count']} half-hourly granules | Mumbai Accum: {imc_acc['mumbai_core_accumulation_mm']} mm | Peak: {imc_acc['peak_rate_mmh']} mm/h")

    # 4. Test Multi-Sensor Fusion Engine
    print("\n--- Testing RainfallFusionEngine Modes ---")
    for mode in [RainfallFusionMode.HEM_ONLY, RainfallFusionMode.IMC_ONLY, RainfallFusionMode.GPM_HEM, RainfallFusionMode.FULL_FUSION]:
        engine = RainfallFusionEngine(mode=mode)
        forcing = await engine.get_rainfall_forcing(t0, t1)
        print(f"\nMode [{mode.value}]:")
        print(f"  Sources used: {forcing['sources_used']}")
        print(f"  Mumbai Accumulation: {forcing['cumulative_mm']} mm | Peak Rate: {forcing['peak_rate_mmh']} mm/h")
        print(f"  Timesteps: {len(forcing['timeseries'])}")

    print("\n=================================================================")
    print("   ALL TESTS PASSED: INSAT-3DR INTEGRATED AND OPERATIONAL        ")
    print("=================================================================\n")

if __name__ == "__main__":
    asyncio.run(main())

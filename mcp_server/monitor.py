import time
from .models import DeployedInstance


def get_spend(instance: DeployedInstance) -> dict:
    uptime_hours = (time.time() - instance.deployed_at) / 3600
    cost = uptime_hours * instance.price_per_hr
    return {
        "provider": instance.provider,
        "gpu_type": instance.gpu_type,
        "uptime_hours": round(uptime_hours, 3),
        "price_per_hr": instance.price_per_hr,
        "total_cost_usd": round(cost, 4),
    }

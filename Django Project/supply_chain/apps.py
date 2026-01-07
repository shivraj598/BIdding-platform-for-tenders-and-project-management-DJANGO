# from django.apps import AppConfig

# class SupplyChainConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'supply_chain'
    
from django.apps import AppConfig

class SupplyChainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'supply_chain'    
    def ready(self):
        # Import signals when app is ready
        import supply_chain.signals_impl
import sys, types
# Stub external deps for import-time only
folium = types.ModuleType('folium')
class DummyRoot:
    def __init__(self):
        self.html = types.SimpleNamespace(add_child=lambda *a, **k: None)
        self.script = types.SimpleNamespace(add_child=lambda *a, **k: None)
    def render(self):
        return ''
class DummyMap:
    def __init__(self, *a, **k):
        pass
    def get_name(self):
        return 'map'
    def get_root(self):
        return DummyRoot()
class Dummy:
    def __init__(self, *a, **k): pass
    def add_to(self, *a, **k): return self
folium.Map = DummyMap
folium.Element = lambda *a, **k: None
# Create submodules
plugins = types.ModuleType('folium.plugins')
plugins.MarkerCluster = Dummy
features = types.ModuleType('folium.features')
features.CustomIcon = Dummy
base = types.ModuleType('folium.base')
# Add top-level names
folium.FeatureGroup = Dummy
folium.LayerControl = Dummy
folium.Marker = Dummy
folium.Popup = Dummy
folium.IFrame = Dummy
folium.plugins = plugins
folium.features = features
sys.modules['folium'] = folium
sys.modules['folium.plugins'] = plugins
sys.modules['folium.features'] = features
# Stub babel.dates
babel = types.ModuleType('babel')
dates = types.ModuleType('babel.dates')
dates.format_datetime = lambda *a, **k: ''
sys.modules['babel'] = babel
sys.modules['babel.dates'] = dates
from app import create_app
app = create_app()
print('OK blueprints', sorted(app.blueprints.keys()))
client = app.test_client()
paths = ['/', '/edit-sites/', '/type-sites/', '/regions/', '/contrats/liste', '/notif/', '/maintenance/', '/champs/']
for p in paths:
    resp = client.get(p, follow_redirects=False)
    print(p, resp.status_code, resp.headers.get('Location'))

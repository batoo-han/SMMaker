import os, sys
stub_path = os.path.join(os.path.dirname(__file__), 'stubs')
if os.path.isdir(stub_path) and stub_path not in sys.path:
    sys.path.insert(0, stub_path)

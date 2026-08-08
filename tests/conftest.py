import os

# Ohne Display laufen die Qt-Tests sonst gar nicht erst an.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

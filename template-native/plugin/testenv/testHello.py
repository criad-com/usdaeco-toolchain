from pxr import Plug, Tf

plugin = Plug.Registry().GetPluginWithName("usdAecoExampleHello")
assert plugin and not plugin.isLoaded
assert plugin.Load() and plugin.isLoaded
registered = Tf.Type.FindByName("AecoExampleHello")
assert registered and Plug.Registry().GetPluginForType(registered) == plugin
assert registered.typeName == "AecoExampleHello"
print("native plugin: 1 loaded Tf type OK")

from pxr import Plug, Tf, Usd, UsdAecoExampleNative

plugin = Plug.Registry().GetPluginWithName("usdAecoExampleNative")
assert plugin and plugin.Load()
record_type = Tf.Type.FindByName("UsdAecoExampleNativeRecord")
assert record_type and Plug.Registry().GetPluginForType(record_type) == plugin
stage = Usd.Stage.CreateInMemory()
record = UsdAecoExampleNative.Record.Define(stage, "/Greeting")
assert record and record.GetPrim().IsA(UsdAecoExampleNative.Record)
assert record.GetPrim().GetAttribute("aeco:exampleNative:message").Get() == "hello"
record.GetPrim().GetAttribute("aeco:exampleNative:message").Set("welcome")
assert record.GetPrim().GetAttribute("aeco:exampleNative:message").Get() == "welcome"
print("codeful schema: 1 type, Python import, fallback and authored value OK")

# Native plugin templates

`schema/` is a codeful schema with one record referent. `plugin/` is a Tf type
registration plugin. Both consume the shared out-of-tree CMake scaffold.

From the toolchain root:

```sh
nix build .#template-native-schema .#template-native-plugin
```

Copy either directory into a new repository, rename its library in library.json,
CMakeLists.txt and the module/descriptor, and call the corresponding builder.
The schema additionally names its include path in GLOBAL.libraryPath. Keep
module.cpp and __init__.py; usdGenSchema generates the classes and wrappers.
The [native guide](../docs/native.md) explains dependencies, installation,
Python imports, runtime discovery and local input overrides.

The record is an isolated tutorial referent. It introduces no spatial, grouping,
geometry or identity mechanism. The [stage](schema/examples/minimal.usda)
composes as a Scope without the plugin through fallbackPrimTypes.

# Rendering example evidence

```sh
env -u PYTHONPATH usdaeco-render stage.usda --cameras inputs/cameras.usda
env -u PYTHONPATH usdaeco-render stage.usda --cameras inputs/cameras.usda --frames 1:3:1
```

| Setting | Contract |
|---|---|
| Cameras | Named Camera children of /Renders; select with repeatable --view |
| Size | --size 1280x800 by default; neither dimension may exceed 1600 |
| Renderer | usdrecord, GPU disabled, Embree, purposes proxy,render; default-purpose geometry is always included |
| Guides | Opt in with --purposes guide,proxy,render (Python: render(..., purposes="guide,proxy,render")) |
| Environment | HDEMBREE_AMBIENT_OCCLUSION_SAMPLES=0; inherited PYTHONPATH cleared |
| Stills | renders/<view>.png |
| Frames | Inclusive decimal start:end:step; up to 240 frames per invocation |
| Animation artifacts | renders/<view>.<frame>.png and <view>.sheet.png; <view>.gif when Pillow is installed |
| Sheet | Numpy tiling, scaled without aspect distortion within the requested size |
| GIF | 64-colour preview, reduced to fit the same byte cap; optional Pillow |
| Content | Valid RGB/RGBA PNG, non-uniform pixels, ≤400000 bytes, dimensions verified |
| Manifest | SHA-256, dimensions and byte sizes; unrelated named views retained |
| Source safety | Camera aspect adjustment is in a temporary stronger layer; source files unchanged |

Identical names, cameras and dimensions are deterministic. Pixel hashes record
actual outputs; cross-version or cross-platform bit-identical Embree pixels are
not promised. Failed renders do not update the manifest. Keep large frame sets
outside committed artifacts unless every file remains within the caps.

Guide-only stages fail before recording with a cause and remedy: no
proxy/render-purpose geometry; add a proxy body or pass
`--purposes guide,proxy,render`. Purpose inherited from a parent counts.
Uniform images still fail; empty stages name the missing geometry, while
other uniform renders suggest checking camera framing and visibility.

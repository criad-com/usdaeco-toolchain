# Example on the demo data centre

Inputs: pinned `dist/base/dc.usda`, with layers in inputs/ applied above it.
Set AECO_DATACENTRE_ROOT to the release checkout. AECO_DATACENTRE_STAGE is a
temporary stage override. Without either, the starter uses the minimal stage.

```sh
env -u PYTHONPATH python examples/datacentre/run.py
```

Open the committed [result](result/README.md) without generating anything:

```sh
usdview examples/datacentre/result/example.usdc
```

Fresh outputs are transient in out/. Findings must match expected/findings.json.
Use `--publish` to refresh committed result/, renders and manifest after review of the
outputs. It never replaces expected findings. The manifest records the actual
source mode and hashes; a minimal run does not prove data-centre integration.
The result contains the flattened stage and the example's own text layers;
source layers are recorded by hash. The total cap is 10,000,000 bytes, with
2,000,000 bytes per USDA layer. The checker compares text layers byte for byte
and the crate through Sdf's canonical USDA serialization.

[result/vanilla.png](result/vanilla.png) is the committed stock USD render proof.
S28 independently re-renders the committed crate without family plugins.

# SPH sample pack

Five cheap SPH solves intended as visual probes before investing in more elaborate scenes.

| case | idea |
|---|---|
| `dam-break` | baseline dam break |
| `tall-column` | tall narrow column collapse |
| `falling-slug` | falling fluid block into a shallow pool |
| `two-towers` | two columns collapse and merge |
| `tilted-surge` | shallow fluid under gravity with a horizontal component |

Each matrix job runs its own SPlisHSPlasH solve for 2 seconds at 12 exported FPS using a coarse 0.07 m particle radius. The VTK particles are compacted to NPZ, authored as an animated vertex-only USD, then rendered in Blender 4.0.2 with Geometry Nodes:

`Mesh to Points -> Instance on Points -> Realize Instances`

The first pass intentionally favors cheap, readable particle visualization over a reconstructed surface. Once a case looks interesting, it can be promoted to a longer/higher-resolution solve or to the existing Points-to-Volume surface pipeline.

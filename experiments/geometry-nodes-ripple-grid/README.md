# Geometry Nodes Ripple Grid

Small Blender 4.0.2 Geometry Nodes sample for the shared \`tmp-blender\` experiment pipeline.

The node graph generates a \`31 x 31\` grid, displaces its vertices with a radial sine wave, converts the vertices to points, instances Icospheres on the points, and realizes the instances for a concrete evaluated mesh.

## Geometry Nodes graph

\`\`\`text
Grid
  -> Set Position
       ^ Position -> Length -> Multiply -> Sine -> Multiply -> Combine XYZ
  -> Mesh to Points
  -> Instance on Points
       ^ Ico Sphere -> Set Material
  -> Realize Instances
  -> Group Output
\`\`\`

## Contract

- \`scene.py\` builds the node group with Blender's Python API and renders \`output/render.png\`.
- \`scene.py\` saves the inspectable source scene as \`output/geometry-nodes.blend\`.
- \`scene.py\` also writes \`output/geometry-nodes-report.json\` with node types and evaluated mesh counts.
- \`validate.py\` checks both the visible render and the evaluated Geometry Nodes result.
- \`experiment.json\` publishes the \`.blend\` file to Git when it stays under the repository safety limit.

Expected full outputs:

- \`render.png\`
- \`geometry-nodes.blend\`
- \`geometry-nodes-report.json\`
- \`validation.json\`
- \`blender-version.txt\`

## License / ライセンス

Code in this experiment is MIT-0. Generated Blender files, renders, videos, and other generated assets are CC0-1.0 unless otherwise noted. Third-party data/assets/source material remain subject to their original licenses and terms.

この実験のコードは MIT-0、生成された Blender ファイル・画像・動画・その他の生成アセットは、特記のない限り CC0-1.0 です。第三者由来のデータ・アセット・素材・ソースを利用している部分は、利用元のライセンスおよび利用条件に従います。

See ../../LICENSE and ../../LICENSES/.

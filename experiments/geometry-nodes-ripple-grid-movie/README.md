# Geometry Nodes Ripple Grid Movie

Animated Blender 4.0.2 Geometry Nodes sample for the shared \`tmp-blender\` experiment pipeline.

This movie version extends the still-image ripple-grid sample by introducing \`Scene Time\` into the node graph, rendering a short MP4 animation, and keeping a preview still plus an inspectable \`.blend\` file.

## Geometry Nodes graph

\`\`\`text
Grid
  -> Set Position
       ^ Position -> Length -> Multiply
       ^ Scene Time -> Multiply
       ^ (radial term + time term) -> Sine -> Multiply -> Combine XYZ
  -> Mesh to Points
  -> Instance on Points
       ^ Ico Sphere -> Set Material
  -> Realize Instances
  -> Group Output
\`\`\`

## Animation contract

- \`scene.py\` builds the node group with Blender's Python API.
- \`scene.py\` renders a mid-animation still as \`output/preview.png\`.
- \`scene.py\` renders a short movie as \`output/ripple-grid.mp4\`.
- \`scene.py\` saves the source scene as \`output/geometry-nodes-movie.blend\`.
- \`scene.py\` writes \`output/geometry-nodes-report.json\` with node types and evaluated mesh counts.
- \`validate.py\` checks the preview image, the MP4 metadata, and the evaluated Geometry Nodes result.
- \`experiment.json\` publishes the \`.blend\` file to Git when it stays under the repository safety limit.

Expected full outputs:

- \`preview.png\`
- \`ripple-grid.mp4\`
- \`geometry-nodes-movie.blend\`
- \`geometry-nodes-report.json\`
- \`validation.json\`
- \`blender-version.txt\`

## License / ライセンス

Code in this experiment is MIT-0. Generated Blender files, renders, videos, and other generated assets are CC0-1.0 unless otherwise noted. Third-party data/assets/source material remain subject to their original licenses and terms.

この実験のコードは MIT-0、生成された Blender ファイル・画像・動画・その他の生成アセットは、特記のない限り CC0-1.0 です。第三者由来のデータ・アセット・素材・ソースを利用している部分は、利用元のライセンスおよび利用条件に従います。

See ../../LICENSE and ../../LICENSES/.

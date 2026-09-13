<!-- template: tla-diagram-conventions/1 -->
# Diagram Conventions

## Tool and files
- **draw.io (diagrams.net)**, saved as **`.drawio.svg`** — the file is both the editable diagram and the image GitHub
  shows. Open it in diagrams.net (web or desktop) or an editor extension.
- One diagram per file in `03-architecture/diagrams/`, named for the question it answers
  (for example `where-is-authorisation-enforced.drawio.svg`).

## Rules
1. **Every diagram answers one question**, and that question is its title.
2. **Draw only diagrams that answer a useful question:** solution, logical, data flow, identity flow, trust boundaries,
   sequence, deployment.
3. **Boundaries are labelled with what changes across them** — identity, authority, data classification or network.
4. **Enforcement points are labelled `ENFORCES: <decision>`**, so the control is visible where it happens.
5. **Flows are numbered**, and the numbers match the sequence diagram and the threat model's attack paths.
6. **Labelled boxes by default.** Vendor icons only when they genuinely aid recognition and comply with the vendor's
   published usage guidelines.
7. **Model relationships; do not decorate.** No decorative imagery, gradients or 3D.
8. **Legible when small:** text readable in a video frame and in a pull-request preview.
9. **Include a legend** when a line style or colour carries meaning.

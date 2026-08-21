Output assets/demo-trace.gif

Set FontSize 16
Set Width 1200
Set Height 620
Set Padding 16
Set Theme "Dracula"
Set Shell "bash"

# The 10-minute happy path: try the co-iteration loop with the bundled example
# (no API key, no Lean). demo.yml has already `pip install -e .`. The --stub
# backend serves the bundled sum_naturals example regardless of the claim text.
Type "proofloop prove 'the sum of the first n naturals is n times n plus 1 over 2' --trace --stub"
Enter
Sleep 6

# Inspect the machine-checkable certificate.
Type "cat certificate.json"
Enter
Sleep 4

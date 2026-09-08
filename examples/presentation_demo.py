import json, pathlib, subprocess, tempfile
with tempfile.TemporaryDirectory(prefix="proofloop-demo-") as folder:
    subprocess.run([".venv/bin/proofloop", "prove", "sum of the first n natural numbers", "--stub", "--max-iter", "3", "--out-dir", folder], capture_output=True, text=True, check=True)
    cert = json.loads((pathlib.Path(folder) / "certificate.json").read_text())
    print(json.dumps({"model":cert["model"], "checker":cert["lean_version"], "simulated_proof_passed":cert["proof_passed"], "iteration_results":[item["lean_ok"] for item in cert["iterations"]], "files":sorted(p.name for p in pathlib.Path(folder).iterdir())}, indent=2))

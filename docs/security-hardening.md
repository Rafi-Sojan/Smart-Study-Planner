# Security hardening and the October 2026 disclosure wave

## Scope

“Black October” is an informal label used for a group of security disclosures
and supply-chain incidents reported during October 2026. It is not a single
software package or one vulnerability that can be patched in this repository.
This project is a Python application and has no PHP or Node.js runtime. The
relevant control is therefore a dependency audit of the Python environment and
the CI supply chain.

## Findings and remediation

The dependency audit was run with `pip-audit` against `requirements.txt`.
The following confirmed findings were remediated:

| Package | Previous version | Remediation |
|---|---:|---|
| `pytest` | 8.3.3 | Pinned to 9.0.3, which contains the reported fix |
| `fastapi` | 0.115.6 | Upgraded to 0.161.1 |
| `starlette` | 0.41.3 | Explicitly pinned to 1.9.0, compatible with the upgraded FastAPI release |

The repository CI now runs:

```powershell
python -m pip install pip-audit==2.10.1
pip-audit -r requirements.txt --ignore PYSEC-2026-2447
```

## Remaining transitive risk: DiskCache

`diskcache==5.6.3` is pulled in by `dvc-data`, which is required for the
project’s DVC workflow. The advisory is CVE-2025-69872 / GHSA-w8v5-vhqr-4h9v
(`PYSEC-2026-2447`): DiskCache uses Python pickle serialization by default,
which can permit code execution when an attacker can write a malicious cache
file and a victim later reads it. The GitHub Advisory Database currently lists
no patched DiskCache release.

This project does not expose its DVC cache as an application upload directory,
and CI does not execute untrusted DVC cache contents. The CI audit therefore
ignores only this one unresolved transitive advisory, while retaining the
finding in this document. DVC cache directories must not be shared with
untrusted users or populated from untrusted artifacts. Any future patched
DiskCache release must replace this exception and remove the CI ignore.

The serving image uses the API-only `requirements-api.txt` dependency set and
does not install DVC or its storage adapters. The full `requirements.txt` set
remains necessary for local data pipelines and CI, so its residual advisory is
still audited and explicitly documented rather than hidden.

Reference: [GitHub Advisory GHSA-w8v5-vhqr-4h9v](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v).

## Operational controls

- Do not add PHP, Node.js, or third-party services to the deployment image
  without adding them to the dependency inventory and audit scope.
- Keep DVC credentials in local configuration or CI secrets; never commit
  access tokens.
- Keep the FastAPI documentation endpoints disabled by default in deployment.
- Run the dependency audit on every CI build and after dependency changes.
- Re-evaluate the DiskCache exception whenever DVC or `dvc-data` releases a
  newer version.

## Verification command

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\pip-audit.exe -r requirements.txt --ignore PYSEC-2026-2447
.\.venv\Scripts\ruff.exe check src pipeline tests
.\.venv\Scripts\python.exe -m pytest -q
```

The ignored advisory is a documented residual risk, not a claim that the
environment is vulnerability-free.

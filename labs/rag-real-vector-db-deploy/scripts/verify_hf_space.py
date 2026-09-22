#!/usr/bin/env python3
"""Static checks on the Hugging Face Spaces deliverable (hf_space/).

Not part of the LAB_TARGET=starter/solution contract on purpose: hf_space/ is a single,
un-split deliverable (there is no "starter" vs "solution" version of a Gradio app to
push), so it cannot honour this repo's "every starter test must fail" rule the way
tests/ does. Run it directly instead:

    python scripts/verify_hf_space.py

These checks do NOT deploy anything and do NOT need gradio installed locally - they
only parse/compile files that already exist on disk. Actually pushing this to Hugging
Face and getting a public URL is a manual step documented in the lab README (no HF
account exists in the sandbox this was built in); nothing here claims a real deploy
happened.
"""

from __future__ import annotations

import py_compile
import sys
from pathlib import Path

HF_SPACE_DIR = Path(__file__).resolve().parent.parent / "hf_space"


def check_app_py_exists_and_compiles() -> None:
    app_path = HF_SPACE_DIR / "app.py"
    assert app_path.is_file(), "hf_space/app.py is missing"
    py_compile.compile(str(app_path), doraise=True)


def check_app_py_defines_a_gradio_demo_and_launches_it() -> None:
    source = (HF_SPACE_DIR / "app.py").read_text()
    assert "import gradio as gr" in source
    assert "demo = gr.Interface(" in source or "demo = gr.Blocks(" in source
    assert "demo.launch()" in source


def check_app_py_reads_the_embedding_key_from_environment_not_hardcoded() -> None:
    source = (HF_SPACE_DIR / "app.py").read_text()
    assert 'os.environ.get("EMBEDDING_API_KEY")' in source
    assert "sk-" not in source, "a hardcoded-looking credential prefix was found in app.py"


def check_requirements_txt_pins_the_real_dependencies() -> None:
    requirements = (HF_SPACE_DIR / "requirements.txt").read_text().lower()
    for package in ("gradio", "chromadb", "scikit-learn", "numpy"):
        assert package in requirements, f"hf_space/requirements.txt is missing {package}"


def check_space_readme_has_valid_hf_frontmatter() -> None:
    readme = (HF_SPACE_DIR / "README.md").read_text()
    assert readme.startswith("---\n")
    frontmatter = readme.split("---\n")[1]
    assert "sdk: gradio" in frontmatter
    assert "app_file: app.py" in frontmatter


def check_no_deploy_is_falsely_claimed_in_lab_readme() -> None:
    lab_readme = (HF_SPACE_DIR.parent / "README.md").read_text().lower()
    assert "<your-hf-username>" in lab_readme or "your-username" in lab_readme


CHECKS = [
    check_app_py_exists_and_compiles,
    check_app_py_defines_a_gradio_demo_and_launches_it,
    check_app_py_reads_the_embedding_key_from_environment_not_hardcoded,
    check_requirements_txt_pins_the_real_dependencies,
    check_space_readme_has_valid_hf_frontmatter,
    check_no_deploy_is_falsely_claimed_in_lab_readme,
]


def main() -> int:
    failures = 0
    for check in CHECKS:
        name = check.__name__
        try:
            check()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
        except Exception as exc:  # noqa: BLE001 - report any error, not just AssertionError
            failures += 1
            print(f"ERROR {name}: {exc!r}")
        else:
            print(f"ok   {name}")
    total = len(CHECKS)
    print(f"\n{total - failures}/{total} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

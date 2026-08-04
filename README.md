# Resume builds

Each resume version can live in its own internal folder and keep `_resume.tex` plus any local style or font files it needs. The current general version is stored in `resume-general/`.

Build the current version:

```bash
./scripts/build_resume.sh
```

Every build writes the submission-ready file to `output/pdf/Morgan_Le_Resume.pdf`. The public filename is fixed even when a different internal resume version is selected. Build intermediates are created in the system temporary directory and removed automatically.

To create another version:

1. Duplicate the current resume folder and give it a new version name.
2. Edit `_resume.tex` in that folder.
3. Run the script with the new internal folder name.

For example:

```bash
./scripts/build_resume.sh "resume-data-science"
```

Running a build for another internal version intentionally replaces the existing `Morgan_Le_Resume.pdf`. The script uses the installed `tectonic` command, or the executable specified by `RESUME_TECTONIC_BIN`.

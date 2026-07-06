# Lab Notes

This is the separate lab workflow. It records your screen and microphone, extracts screen frames, reads visible text from those frames when OCR is installed, transcribes audio, and creates a lab breakdown.

## Run

```powershell
.\start_labs.ps1
```

Then open:

```text
http://localhost:8010
```

## Enable Screen Text Reading

OCR needs Tesseract plus the Python wrapper:

```powershell
.\install_lab_ocr.ps1
```

After installing, restart the lab server. New lab recordings will include a `Screen Text` section in the saved lab detail, Markdown notes, combined notes, and PDF export.

## Output

Lab data is separate from lecture notes:

```text
data\labs.db
outputs\labs
```

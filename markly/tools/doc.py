"""Document tools — Phase 11.

- pdf.extract: read_only, extracts text from PDFs in the workspace.
- doc.generate: write_local, writes formatted text/markdown/pdf content.
"""
import os
import shlex
from pathlib import Path
from typing import Dict, Any
from markly.tools.registry import ToolRegistry

def get_sandbox():
    from markly.engine import get_current_sandbox
    return get_current_sandbox()

def pdf_extract(args: Dict[str, Any]) -> str:
    path = args.get("path")
    if not path:
        return "Error: missing 'path'"
        
    sb = get_sandbox()
    
    # We run a small self-contained python script inside the container.
    # It ensures pypdf is installed, extracts the text, and prints it.
    script = f"""
import sys
import subprocess

try:
    import pypdf
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pypdf"])
    import pypdf

try:
    reader = pypdf.PdfReader({repr(path)})
    text = []
    for page in reader.pages:
        text.append(page.extract_text() or "")
    print("\\n--- PAGE BREAK ---\\n".join(text))
except Exception as e:
    print(f"Error reading PDF: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
    sb.write_file(".tmp_pdf_extract.py", script)
    exit_code, output = sb.execute("python .tmp_pdf_extract.py")
    
    # Cleanup tmp script
    sb.execute("rm -f .tmp_pdf_extract.py")
    
    if exit_code != 0:
        return f"Error: PDF extraction failed. Output:\n{output}"
        
    return output

def doc_generate(args: Dict[str, Any]) -> str:
    path = args.get("path")
    content = args.get("content")
    if not path or content is None:
        return "Error: missing 'path' or 'content'"
        
    sb = get_sandbox()
    
    # If the path is a PDF, compile via a Python script inside the container using reportlab
    if path.lower().endswith(".pdf"):
        script = f"""
import sys
import subprocess

try:
    import reportlab
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "reportlab"])
    import reportlab

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

try:
    doc = SimpleDocTemplate({repr(path)}, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    for line in {repr(content)}.split("\\n"):
        if line.strip():
            story.append(Paragraph(line, styles["Normal"]))
            story.append(Spacer(1, 12))
    doc.build(story)
    print("PDF generated successfully.")
except Exception as e:
    print(f"Error building PDF: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
        sb.write_file(".tmp_pdf_gen.py", script)
        exit_code, output = sb.execute("python .tmp_pdf_gen.py")
        sb.execute("rm -f .tmp_pdf_gen.py")
        if exit_code != 0:
            return f"Error: PDF generation failed. Output:\n{output}"
        return f"PDF document successfully generated at {path}"
        
    # Default to writing text/markdown/html directly
    sb.write_file(path, content)
    return f"Document successfully generated at {path}"

def register_doc_tools(registry: ToolRegistry):
    registry.register(
        name="pdf.extract",
        category="doc",
        description="Extract all readable text from a PDF file in the workspace.",
        tier="read_only",
        schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to PDF file"}
            },
            "required": ["path"]
        },
        func=pdf_extract
    )
    
    registry.register(
        name="doc.generate",
        category="doc",
        description="Generate a text, markdown, HTML, or PDF document inside the workspace.",
        tier="write_local",
        schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to output file (e.g. document.pdf, report.md)"},
                "content": {"type": "string", "description": "Content of the document"}
            },
            "required": ["path", "content"]
        },
        func=doc_generate
    )

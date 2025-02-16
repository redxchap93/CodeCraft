import os
import sys
import io
import tempfile
import subprocess
import re  # For sanitizing text and generating repo names
from contextlib import redirect_stdout
from flask import Flask, request, render_template_string, redirect, url_for, session, flash
import ollama  # Ensure this is installed and configured
from github import Github  # pip install PyGithub
import git  # pip install GitPython

app = Flask(__name__)
app.secret_key = "super-secret-key"  # CHANGE THIS for production

# List of available models
MODELS = [
    "deepseek-r1:1.5b",
    "deepseek-r1:latest",
    "qwen2.5:14b",
    "deepseek-coder:latest",  # We'll use this one as the corrector agent.
    "mistral:latest",
    "qwen2.5:7b",
    "mistral-small:latest",
    "JorgeAtLLama/thematrix:latest",
    "nomic-embed-text:latest",
    "qwen2:7b",
    "deepseek-r1:70b",
    "deepseek-r1:32b",
    "deepseek-r1:7b",
    "qwen2:latest",
    "deepseek-r1:14b",
    "phi4:latest",
    "llama3.3:latest",
    "llama2:latest",
    "llama3.1:8b",
    "nichealpham/port-correction:latest",
    "llama3:latest",
    "qwen2.5:latest",
    "llama3.1:latest",
    "llama3.2-vision:latest",
    "llama3.2:latest",
    "phi3:latest"
]

# ---------- Helper Functions ----------
def sanitize_text(text):
    """Remove control characters from text."""
    return re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)

def generate_repo_name(prompt):
    """Generate a sanitized repository name based on the project prompt."""
    # Take the first 5 words (or full prompt if short)
    words = prompt.strip().split()[:5]
    name = "-".join(words)
    # Lowercase, remove non-alphanumeric/dash characters.
    name = re.sub(r'[^a-zA-Z0-9\-]', '', name).lower()
    if not name:
        name = "codecraft-project"
    return name

def submit_project_to_github(project_name, explanation, code_content, language, github_token):
    try:
        # Sanitize explanation to remove control characters.
        safe_explanation = sanitize_text(explanation)
        # Generate repository name.
        repo_name = generate_repo_name(explanation)
        # Connect to GitHub
        g = Github(github_token)
        user = g.get_user()
        # Create a new repository using the generated name.
        repo = user.create_repo(repo_name, description=f"Project generated by CodeCraft Revolution.\n\nExplanation:\n{safe_explanation}")
        # Create a temporary directory to organize project files
        temp_dir = tempfile.mkdtemp()
        # Write files
        readme_path = os.path.join(temp_dir, "README.md")
        code_filename = "main.py" if language=="python" else ("script.sh" if language=="bash" else "script.ps1")
        code_path = os.path.join(temp_dir, code_filename)
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(f"# {repo_name}\n\n{safe_explanation}\n")
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(code_content)
        # Initialize git repo and commit
        repo_local = git.Repo.init(temp_dir)
        repo_local.git.add(all=True)
        repo_local.index.commit("Initial commit from CodeCraft Revolution")
        # Add remote and push
        remote_url = repo.clone_url.replace("https://", f"https://{github_token}@")
        repo_local.create_remote("origin", remote_url)
        repo_local.remote(name="origin").push(refspec="master:master")
        return f"Project successfully submitted to GitHub: {repo.html_url}"
    except Exception as e:
        return f"Error during GitHub submission: {e}"

# ---------- Shared Base Template ----------
base_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ title }}</title>
  <style>
    /* Gorgeous Dark Theme with Developer Flair */
    html, body {
      margin: 0;
      padding: 0;
      height: 100%;
      background: linear-gradient(135deg, #121212, #1e1e1e);
      color: #e0e0e0;
      font-family: Consolas, "Courier New", monospace;
    }
    .nav {
      text-align: center;
      padding: 15px;
      background-color: #1a1a1a;
      box-shadow: 0 2px 4px rgba(0,0,0,0.8);
    }
    .nav a {
      color: #e0e0e0;
      text-decoration: none;
      margin: 0 20px;
      font-size: 18px;
    }
    .nav a:hover {
      text-decoration: underline;
    }
    .container {
      max-width: 900px;
      margin: 30px auto;
      padding: 30px;
      background-color: #1e1e1e;
      border-radius: 8px;
      box-shadow: 0 0 20px rgba(0,0,0,0.5);
    }
    h1 {
      font-size: 2.8em;
      margin-bottom: 20px;
      text-align: center;
    }
    form {
      margin-bottom: 20px;
      text-align: center;
    }
    input[type="text"], select, textarea {
      padding: 10px;
      width: 80%;
      max-width: 600px;
      border: 1px solid #444;
      border-radius: 4px;
      background: #2a2a2a;
      color: #e0e0e0;
      font-size: 18px;
      margin-bottom: 10px;
    }
    textarea {
      height: 250px;
      resize: vertical;
      font-family: Consolas, "Courier New", monospace;
    }
    button {
      padding: 10px 20px;
      border: none;
      border-radius: 4px;
      background: #333;
      color: #e0e0e0;
      font-size: 18px;
      cursor: pointer;
      transition: background 0.3s ease;
      margin: 5px;
    }
    button:hover {
      background: #555;
    }
    .result {
      background: #2a2a2a;
      border: 1px solid #444;
      padding: 20px;
      border-radius: 4px;
      font-size: 18px;
      line-height: 1.5;
      margin-top: 20px;
      height: 300px;
      overflow-y: auto;
    }
    .result::-webkit-scrollbar { width: 0; background: transparent; }
    .result { scrollbar-width: none; }
    .caret {
      display: inline-block;
      background-color: #e0e0e0;
      width: 2px;
      margin-left: 2px;
      animation: blink 0.7s steps(1) infinite;
      vertical-align: bottom;
    }
    @keyframes blink { 50% { opacity: 0; } }
  </style>
</head>
<body>
  <div class="nav">
    <a href="/explain">Explain</a>
    <a href="/codecraft">CodeCraft</a>
    <a href="/github">GitHub Connect</a>
  </div>
  <div class="container">
    <h1>{{ heading }}</h1>
    {{ content|safe }}
  </div>
  <script>
    function typeWriter(text, element, initialSpeed, acceleration) {
      let i = 0;
      element.innerHTML = "";
      let caret = document.createElement("span");
      caret.className = "caret";
      element.appendChild(caret);
      function type() {
        if (i < text.length) {
          caret.insertAdjacentText("beforebegin", text.charAt(i));
          i++;
          let currentSpeed = Math.max(1, initialSpeed - i * acceleration);
          setTimeout(type, currentSpeed);
          element.scrollTop = element.scrollHeight;
        } else {
          caret.remove();
        }
      }
      type();
    }
    window.addEventListener("DOMContentLoaded", function() {
      const resultArea = document.getElementById("resultArea");
      if(resultArea && resultArea.textContent.trim().length > 0) {
        const resultText = resultArea.textContent;
        resultArea.textContent = "";
        typeWriter(resultText, resultArea, 40, 0.8);
      }
    });
  </script>
</body>
</html>
"""

# ---------- Explain Page Template ----------
explain_template = """
{% set content %}
<form method="POST">
  <input type="text" name="prompt" placeholder="Explain a concept..." value="{{ prompt|default('') }}" required><br>
  <select name="model">
    {% for m in models %}
      <option value="{{ m }}" {% if m == selected_model %}selected{% endif %}>{{ m }}</option>
    {% endfor %}
  </select><br>
  <button type="submit" name="action" value="explain">Explain</button>
  <button type="submit" name="action" value="correct_explanation">Correct Explanation</button>
</form>
{% if result %}
<div class="result" id="resultArea">{{ result }}</div>
{% endif %}
{% endset %}
""" + base_template

# ---------- CodeCraft Page Template ----------
codecraft_template = """
{% set content %}
<form method="POST">
  <input type="text" name="prompt" placeholder="Describe the functionality..." value="{{ prompt|default('') }}" required><br>
  <select name="language">
    <option value="python" {% if language=='python' %}selected{% endif %}>Python</option>
    <option value="bash" {% if language=='bash' %}selected{% endif %}>Bash</option>
    <option value="powershell" {% if language=='powershell' %}selected{% endif %}>PowerShell</option>
  </select><br>
  <select name="model">
    {% for m in models %}
      <option value="{{ m }}" {% if m == selected_model %}selected{% endif %}>{{ m }}</option>
    {% endfor %}
  </select><br>
  <!-- Action buttons -->
  <button type="submit" name="action" value="generate">Generate Code</button>
  {% if generated_code %}
    <button type="submit" name="action" value="correct">Correct Code</button>
    <button type="submit" name="action" value="run">Run Code</button>
    <button type="submit" name="action" value="test">Test Code</button>
    <button type="submit" name="action" value="security_test">Security Test Code</button>
    {% if session.github_token %}
      <button type="submit" name="action" value="submit_github">Submit to GitHub</button>
    {% endif %}
  {% endif %}
  <br>
  <!-- Editable Code Editor Area -->
  {% if generated_code %}
    <textarea name="editor_code" placeholder="Edit your code here...">{{ generated_code }}</textarea>
  {% endif %}
</form>
{% if generated_code and action == 'generate' %}
  <h3>Generated Code:</h3>
  <div class="result" id="resultArea" style="white-space: pre;">{{ generated_code }}</div>
{% elif corrected_code %}
  <h3>Corrected Code:</h3>
  <div class="result" id="resultArea" style="white-space: pre;">{{ corrected_code }}</div>
{% endif %}
{% if run_output %}
  <h3>Execution Output:</h3>
  <div class="result" id="outputArea" style="white-space: pre;">{{ run_output }}</div>
{% endif %}
{% if security_output %}
  <h3>Security Test Output:</h3>
  <div class="result" id="outputArea" style="white-space: pre;">{{ security_output }}</div>
{% endif %}
{% if github_message %}
  <h3>GitHub Submission:</h3>
  <div class="result" id="outputArea" style="white-space: pre;">{{ github_message }}</div>
{% endif %}
{% endset %}
""" + base_template

# ---------- GitHub Connection Template ----------
github_template = """
{% set content %}
<form method="POST">
  <input type="text" name="github_token" placeholder="Enter your GitHub Personal Access Token" required><br>
  <button type="submit">Connect to GitHub</button>
</form>
{% if connected %}
  <p>Connected as: {{ github_username }}</p>
{% endif %}
{% endset %}
""" + base_template

# ---------- Helper Functions for Testing, Security & GitHub Submission ----------
def run_python_code(code):
    try:
        f = io.StringIO()
        with redirect_stdout(f):
            exec(code, {'__name__': '__main__'})
        output = f.getvalue()
        return output if output else "Code executed successfully (no output)."
    except Exception as e:
        return f"Error during execution: {e}"

def run_bash_code(code):
    try:
        result = subprocess.run(["bash", "-c", code], capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        return output if output.strip() else "Bash code executed successfully (no output)."
    except Exception as e:
        return f"Error during Bash execution: {e}"

def run_powershell_code(code):
    try:
        shell_cmd = "powershell" if sys.platform.startswith("win") else "pwsh"
        result = subprocess.run([shell_cmd, "-Command", code], capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        return output if output.strip() else "PowerShell code executed successfully (no output)."
    except Exception as e:
        return f"Error during PowerShell execution: {e}"

def run_security_test_python(code):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w", encoding="utf-8") as tmp:
            tmp.write(code)
            tmp_filename = tmp.name
        result = subprocess.run(["bandit", "-r", tmp_filename], capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        os.unlink(tmp_filename)
        return output if output.strip() else "Security test executed successfully (no issues found)."
    except Exception as e:
        return f"Error during security testing: {e}"

def run_security_test(code, language):
    if language == "python":
        return run_security_test_python(code)
    else:
        return f"Security testing is not implemented for {language} code."

# ---------- Routes ----------
@app.route('/github', methods=['GET', 'POST'])
def github_connect():
    connected = False
    github_username = ""
    if request.method == 'POST':
        token = request.form.get("github_token", "")
        if token:
            try:
                g = Github(token)
                user = g.get_user()
                github_username = user.login
                session["github_token"] = token
                connected = True
                flash("GitHub connected successfully!", "success")
            except Exception as e:
                flash(f"Failed to connect to GitHub: {e}", "error")
    return render_template_string(github_template,
                                  title="GitHub Connection",
                                  heading="Connect to GitHub",
                                  connected=connected,
                                  github_username=github_username)

@app.route('/explain', methods=['GET', 'POST'])
def explain():
    result = None
    prompt = ""
    selected_model = MODELS[0]
    action = request.form.get('action', '')
    if request.method == 'POST':
        prompt = request.form.get('prompt', '')
        selected_model = request.form.get('model', MODELS[0])
        if action == "correct_explanation":
            correct_prompt = f"Correct and improve the following explanation:\n\n{prompt}"
            try:
                response = ollama.generate(model="deepseek-coder:latest", prompt=correct_prompt)
                result = response.get('response', 'No correction generated.')
            except Exception as e:
                result = f"An error occurred during correction: {e}"
        else:
            try:
                response = ollama.generate(model=selected_model, prompt=prompt)
                result = response.get('response', 'No response from model.')
            except Exception as e:
                result = f"An error occurred: {e}"
    return render_template_string(explain_template,
                                  title="Explain Concepts",
                                  heading="Explain Concepts",
                                  prompt=prompt,
                                  result=result,
                                  models=MODELS,
                                  selected_model=selected_model)

@app.route('/codecraft', methods=['GET', 'POST'])
def codecraft():
    generated_code = None
    corrected_code = None
    run_output = None
    security_output = None
    github_message = None
    prompt = ""
    language = "python"
    selected_model = MODELS[0]
    action = request.form.get('action', '')
    editor_code = ""
    
    if request.method == 'POST':
        prompt = request.form.get('prompt', '')
        language = request.form.get('language', 'python')
        selected_model = request.form.get('model', MODELS[0])
        editor_code = request.form.get('editor_code', '')
        
        if action == "generate":
            full_prompt = f"Generate {language} code for the following requirement:\n\n{prompt}"
            try:
                response = ollama.generate(model=selected_model, prompt=full_prompt)
                generated_code = response.get('response', 'No code generated.')
            except Exception as e:
                generated_code = f"An error occurred during code generation: {e}"
        elif action == "correct":
            if editor_code.strip():
                correction_prompt = f"Correct the following {language} code to fix errors and improve its quality:\n\n{editor_code}"
                try:
                    response = ollama.generate(model="deepseek-coder:latest", prompt=correction_prompt)
                    corrected_code = response.get('response', 'No correction generated.')
                except Exception as e:
                    corrected_code = f"An error occurred during code correction: {e}"
            else:
                corrected_code = "No code available to correct."
        elif action == "run":
            if editor_code.strip():
                if language == "python":
                    run_output = run_python_code(editor_code)
                elif language == "bash":
                    run_output = run_bash_code(editor_code)
                elif language == "powershell":
                    run_output = run_powershell_code(editor_code)
                else:
                    run_output = "Unsupported language for execution."
            else:
                run_output = "No code available to run."
        elif action == "test":
            if editor_code.strip():
                if language == "python":
                    run_output = run_python_code(editor_code)
                elif language == "bash":
                    run_output = run_bash_code(editor_code)
                elif language == "powershell":
                    run_output = run_powershell_code(editor_code)
                else:
                    run_output = "Unsupported language for testing."
            else:
                run_output = "No code available to test."
        elif action == "security_test":
            if editor_code.strip():
                security_output = run_security_test(editor_code, language)
            else:
                security_output = "No code available to test for security."
        elif action == "submit_github":
            if editor_code.strip() and prompt.strip():
                project_name = generate_repo_name(prompt)
                token = session.get("github_token", None)
                if token:
                    github_message = submit_project_to_github(project_name, prompt, editor_code, language, token)
                else:
                    github_message = "Not connected to GitHub. Please connect first."
            else:
                github_message = "No project code/explanation available."
        if not generated_code and not corrected_code:
            generated_code = editor_code
    
    return render_template_string(codecraft_template,
                                  title="CodeCraft Revolution",
                                  heading="CodeCraft Revolution",
                                  prompt=prompt,
                                  generated_code=generated_code,
                                  corrected_code=corrected_code,
                                  run_output=run_output,
                                  security_output=security_output,
                                  github_message=github_message,
                                  models=MODELS,
                                  selected_model=selected_model,
                                  language=language,
                                  action=action)

@app.route('/')
def index():
    return redirect(url_for('codecraft'))

if __name__ == '__main__':
    app.run(debug=True)

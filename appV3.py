import os
import subprocess
import json
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='templates3')

# Configuration
FIREBASE_CLI_PATH = r"C:/Users/Administrator/AppData/Roaming/npm/firebase.cmd"
PROJECTS_ROOT = r"C:/Users/Administrator/Desktop/firebase" 

def get_project_folders():
    folders = []
    try:
        for item in os.listdir(PROJECTS_ROOT):
            item_path = os.path.join(PROJECTS_ROOT, item)
            if os.path.isdir(item_path):
                folders.append(item)
    except Exception as e:
        print(f"[ERROR] Failed to list projects: {e}")
    return sorted(folders)

def get_all_folders(project_folder):
    project_path = os.path.join(PROJECTS_ROOT, project_folder)
    folders = []
    try:
        for item in os.listdir(project_path):
            item_path = os.path.join(project_path, item)
            if os.path.isdir(item_path):
                folders.append(item)
    except Exception as e:
        print(f"[ERROR] Failed to list folders in {project_folder}: {e}")
    return sorted(folders)

def ensure_firebase_json(project_folder, target, public_dir, redirect_url):
    project_path = os.path.join(PROJECTS_ROOT, project_folder)
    firebase_config_path = os.path.join(project_path, 'firebase.json')
    
    config = {"hosting": []}
    if os.path.exists(firebase_config_path):
        try:
            with open(firebase_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except: pass

    # FIXED LOGIC: Respects http if provided, only adds https if NO protocol is found
    if not redirect_url.lower().startswith(('http://', 'https://')):
        redirect_url = 'https://' + redirect_url
    
    base_url = redirect_url.rstrip('/')
    
    new_hosting_entry = {
        "target": target,
        "public": public_dir,
        "ignore": ["firebase-debug.log", "firebase-debug.*.log"],
        "redirects": [
            {
                "source": "**",
                "destination": f"{base_url}/:splat",
                "type": 301
            }
        ],
        "rewrites": [
            {
                "source": "**",
                "destination": "/index.html"
            }
        ],
        "cleanUrls": False,
        "trailingSlash": False
    }

    if not isinstance(config.get('hosting'), list):
        config['hosting'] = []
    
    config['hosting'] = [item for item in config['hosting'] if item.get('target') != target]
    config['hosting'].append(new_hosting_entry)

    with open(firebase_config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

@app.route('/')
def index():
    projects = get_project_folders()
    return render_template('index.html', projects=projects)

@app.route('/get-public-folders', methods=['POST'])
def get_public_folders_route():
    data = request.json
    project = data.get('project')
    folders = get_all_folders(project)
    return jsonify({'success': True, 'folders': folders})

@app.route('/deploy', methods=['POST'])
def deploy():
    data = request.json
    project = data.get('project')
    folder = data.get('folder') 
    site_name = data.get('siteName', '').strip()
    redirect_url = data.get('redirectUrl', '').strip()
    
    project_path = os.path.join(PROJECTS_ROOT, project)
    folder_path = os.path.join(project_path, folder)
    
    # Ensure protocol is handled correctly for the HTML files too
    if not redirect_url.lower().startswith(('http://', 'https://')):
        redirect_url = 'https://' + redirect_url
    clean_dest = redirect_url.rstrip('/')

    try:
        os.makedirs(folder_path, exist_ok=True)

        # Updated JavaScript Failsafe to respect exactly what is in redirect_url
        failsafe_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Redirecting...</title>
    <script>
        // Directly using the destination as typed
        window.location.href = "{clean_dest}" + window.location.pathname + window.location.search;
    </script>
</head>
<body>Redirecting to {clean_dest}...</body>
</html>"""

        for filename in ['index.html', '404.html']:
            with open(os.path.join(folder_path, filename), 'w', encoding='utf-8') as f:
                f.write(failsafe_content)
        
        ensure_firebase_json(project, site_name, folder, redirect_url)
        
        run_firebase_command(project, ['target:apply', 'hosting', site_name, site_name])
        deploy_result = run_firebase_command(project, ['deploy', '--only', f'hosting:{site_name}'])
        
        if deploy_result['success']:
            return jsonify({'success': True, 'message': f'Successfully deployed to {clean_dest}'})
        else:
            return jsonify({'success': False, 'error': deploy_result.get('error')})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def run_firebase_command(project_folder, args):
    project_path = os.path.join(PROJECTS_ROOT, project_folder)
    try:
        result = subprocess.run(
            [FIREBASE_CLI_PATH] + args,
            capture_output=True,
            text=True,
            cwd=project_path,
            timeout=120,
            encoding='utf-8'
        )
        return {'success': result.returncode == 0, 'output': result.stdout, 'error': result.stderr}
    except Exception as e:
        return {'success': False, 'output': '', 'error': str(e)}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

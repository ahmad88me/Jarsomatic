from flask import Flask, request
import ConfigParser
# import json
# import simplejson as json
import rson as json
import re
from subprocess import call
import os.path
import random
import string
from github import Github

TEST = True
repo_name = None  # set in get_repo_from_payload
repo_rel_dir = ''.join([random.choice(string.ascii_letters+string.digits) for _ in range(9)])
app = Flask(__name__)
app_home = os.path.dirname( os.path.abspath(__file__))
config_file = 'jarsomatic.cfg'
config = ConfigParser.ConfigParser()
if not os.path.isfile(os.path.join(app_home, config_file)):
    print "\n*** The file: "+config_file+" is not here or is not accessible ***\n"
config.read(os.path.join(app_home, config_file))
github_token = config.get('GITHUB', 'token')
temp_dir = config.get('DEFAULT', 'tmp')
g = Github(github_token)

try:
    g.get_user().login
except Exception as e:
    print "Github token is invalid"


@app.route("/")
def hello():
    return "Welcome to Jarsomatic" + "<br><br><a href='testp'>Test Positive</a>" + \
           "<br><br><a href='testn'>Test Negative</a>"


@app.route("/testp", methods=["GET"])
def test_positive():
    d = os.path.join(app_home, "webhook_example_positive.txt")
    f = open(d)
    file_content = f.read()
    return webhook_handler(file_content)


@app.route("/testn", methods=["GET"])
def test_negative():
    d = os.path.join(app_home, "webhook_example_negative.txt")
    f = open(d)
    file_content = f.read()
    return webhook_handler(file_content)


@app.route("/webhook", methods=["POST"])
def webhook():
    values = request.values['payload']
    return webhook_handler(values)


def webhook_handler(payload_text):
    values = payload_text
    try:
        values = json.loads(str(values))
        payload = values['payload']
    except Exception as e:
        print "exception: "+str(e)
        return "exception occurred"
    print "will get changed files from payload"
    changed_files = get_changed_files_from_payload(payload)
    print "will get the repo from payload"
    repo_str = get_repo_from_payload(payload)
    print "will proceed to the workflow"
    return workflow(changed_files, repo_str)
    # return run_if_target(changed_files)


def get_changed_files_from_commit(commit):
    return commit["added"] + commit["modified"]


def get_changed_files_from_payload(payload):
    commits = payload['commits']
    changed_files = []
    for c in commits:
        changed_files += get_changed_files_from_commit(c)
    return changed_files


def get_repo_from_payload(payload):
    global repo_name
    # print "will get fullname"
    # for k in payload["repository"]:
    #     print "k: %s"%(k)
    r = payload["repository"]["full_name"]
    # print "will get name"
    repo_name = payload["repository"]["name"]
    # print "repository: %s"%(r)
    return r


def create_pull_request(repo_str):
    global g
    username = g.get_user().login
    repo = g.get_repo(repo_str)
    title = 'Jarsomatic'
    body = 'Jarsomatic pull request'
    try:
        repo.create_pull(head=username+':master', base='master', title=title, body=body)
        return True
    except Exception as e:
        print "cannot create pull request, error:  <%s>"%(str(e))
        return False


def fork_repo(repo_str):
    global g
    u = g.get_user()
    repo = g.get_repo(repo_str)
    try:
        f = u.create_fork(repo)
        return f.clone_url
    except Exception as e:
        print "error forking the repo %s, <%s>"%(repo_str, str(e))


def run_if_target(changed_files, target_files, jar_command):
    jarsomatic_branch = "jarsomatic"
    print "found %d files"%(len(changed_files))
    found = False
    for f in changed_files:
        for t in target_files:
            if t == f:
                found = True
                break
        if found:
            break
    if found:
        print "Run"
        comm = "cd "+os.path.join(temp_dir, repo_rel_dir, repo_name)+"; "  # Go to the project location
        if not TEST:
            comm += "git pull; "  # get latest update
        comm += jar_command  # run the command and generate the output
        call(comm, shell=True)
        comm = "cd "+temp_dir+"; rm -Rf "+repo_rel_dir
        call(comm, shell=True)
        return "Run: "+comm
    else:
        comm = "cd "+temp_dir+"; rm -Rf "+repo_rel_dir
        call(comm, shell=True)
        print "Ignore"
        return "Ignore"


# source: http://stackoverflow.com/questions/21495598/simplejson-encoding-issue-illegal-character
def remove_control_chars(s):
    control_chars = ''.join(map(unichr, range(0, 32) + range(127, 160)))
    control_char_re = re.compile('[%s]' % re.escape(control_chars))
    return control_char_re.sub('', s)


def clone_repo(repo_url):
    comm = "cd %s; mkdir %s ;git clone %s"%(temp_dir, repo_rel_dir, repo_url)
    call(comm, shell=True)


def copy_repo():

    comm = "mkdir %s"%(os.path.join(temp_dir, repo_rel_dir))
    # target is the repo name in the test webhook example so the example work
    comm += "; cp -R %s %s"%(os.path.join(temp_dir, 'source'), os.path.join(temp_dir, repo_rel_dir, 'target'))
    print "copy command: "+comm
    call(comm, shell=True)
    print "command executed"


def workflow(changed_files, repo_str):
    if TEST:
        print "coping the source repo"
        copy_repo()
    else:
        print "forking the repo"
        repo_url = fork_repo(repo_str)
        print "cloning the repo"
        clone_repo(repo_url)
    print "getting jar configurations"
    target_files, jar_command = get_jar_config(os.path.join(temp_dir, repo_rel_dir, repo_name, 'jar.cfg'))
    print "running if target"
    return run_if_target(changed_files, target_files, jar_command)


def get_jar_config(config_file):
    print "looking for: %s"%(config_file)
    confi = ConfigParser.ConfigParser()
    if not os.path.isfile(config_file):
        print "\n*** The file: "+config_file+" is not here or is not accessible ***\n"
    print "read the file"
    confi.read(config_file)
    print "getting the command"
    jar_command = confi.get('DEFAULT', 'command')
    print "target files"
    target_files_str = confi.get('DEFAULT', 'watch')
    print "watch"
    target_files = [f.strip().strip("'").strip('"') for f in target_files_str.split(",")]
    print "target return"
    return target_files, jar_command

if __name__ == "__main__":
    app.run()


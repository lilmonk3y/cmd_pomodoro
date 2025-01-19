import os

def path_to_file(path):
    return os.path.join(os.path.expanduser('~'), path)

def file_path(args, path, file_name):
    return os.path.join("", *[path,"test",file_name]) if args.test else os.path.join(path, file_name)

def file_path_env_agnostic(path, file_name):
    return os.path.join(path, file_name)

def file_path_in_home(*paths):
    return os.path.join(os.path.expanduser('~'), *paths)


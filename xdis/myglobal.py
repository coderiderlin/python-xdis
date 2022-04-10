def init():
    global globals
    globals ={}
def set_val(key,val):
    globals[key]=val

def get_val(key,defval=None):
    try:
        return globals[key]
    except KeyError:
        return defval

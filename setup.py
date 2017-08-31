import py2exe
from distutils.core import setup

setup(console = ["getPR.py"],
      options = { "py2exe":{"compressed" : 1, "optimize" : 2, "bundle_files" : 1, "dll_excludes":["MSVCP90.dll"], "includes":["sip"]}},
      zipfile = None
      )
from setuptools import setup


setup(name="opcua-client-gui-adesso",
      version="0.1.0",
      description="OPC-UA Client GUI build at adesso SE",
      author="U Pohlmann, C Schlüting",
      url='https://gitlab.adesso-group.com/77446dc9/opcua-client-gui',
      packages=["uaclient", "uaclient.theme"],
      license="GNU General Public License",
      install_requires=["asyncua==1.1.5", "opcua-widgets>=0.6.0", "PyQt5", "duckdb==1.0.0"],
      entry_points={'console_scripts':
                    ['opcua-client-adesso = uaclient.mainwindow:main']
                    }
      )

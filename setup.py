from setuptools import setup, find_packages

setup(name='busypenguin',
      version='0.0.0',

      description='Publish slack notifications for tasks using context managers',
      url='https://github.com/kyrias/busypenguin',

      author='Johannes Löthberg',
      author_email='johannes@kyriasis.com',

      license='ISC',

      packages=find_packages(),

      install_requires=['slackclient'])

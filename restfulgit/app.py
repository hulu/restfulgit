# coding=utf-8


from restfulgit.app_factory import create_app


application = create_app()
LOADED_CONFIG = application.config.from_envvar('RESTFULGIT_CONFIG', silent=True)
LOADED_CONFIG = LOADED_CONFIG or application.config.from_pyfile('/etc/restfulgit.conf.py', silent=True)
if not LOADED_CONFIG:
    raise SystemExit("Failed to load any RestfulGit configuration!")


if __name__ == '__main__':
    application.debug = True
    application.run(host='0.0.0.0')

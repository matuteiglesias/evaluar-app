from flask_limiter import Limiter
from flask_wtf.csrf import CSRFProtect

from services.authentication import rate_limit_key


csrf = CSRFProtect()
limiter = Limiter(key_func=rate_limit_key)

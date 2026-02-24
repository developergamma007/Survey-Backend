from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed = "$2b$12$y5THdVd56K2gvIRMlwC5sOK.Am.HGbthUp0L1aPWnzcIP7c6HLT6u"
print(f"Verifying 'admin' against {hashed}")
try:
    result = pwd_context.verify("admin", hashed)
    print(f"Result: {result}")
except Exception as e:
    print(f"Error: {e}")

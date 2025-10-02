-- Seed base 'demo' user with password 'password'
-- Uses a precomputed pbkdf2_sha256 hash compatible with backend auth.verify_password

INSERT INTO users (username, password_hash)
VALUES (
  'demo',
  'pbkdf2_sha256$100000$LD0dr2Z0AMugGAivOrW4YRo/Zy1EFzzTk2WorRIBBkA=$wHq+cSI/hL1mTfuJBUW376/cNSCGCdRxklcr8p/PYYM='
)
ON CONFLICT (username) DO NOTHING;


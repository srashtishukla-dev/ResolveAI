# Account API

## Customer registration

Create a customer account with:

```http
POST /api/auth/register/
Content-Type: application/json
```

```json
{
  "name": "Ada Lovelace",
  "username": "ada",
  "email": "ada@example.com",
  "password": "A-strong-password-123!",
  "password_confirmation": "A-strong-password-123!"
}
```

A successful request returns `201 Created` with the new username:

```json
{
  "detail": "Customer account created successfully.",
  "username": "ada"
}
```

Validation errors return `400 Bad Request` with field-specific messages. Usernames
and email addresses must be unique, passwords must pass Django's configured
password validators, and the two password fields must match.

Passwords are hashed by Django's user manager. Public registration always creates
an active non-staff, non-superuser customer. Administrative fields submitted by a
client are not accepted as registration attributes and cannot grant privileges.

Customers can sign in through `POST /api/token/`, but staff-only AI Assistant and
Knowledge Base operations remain protected by the existing backend permissions.

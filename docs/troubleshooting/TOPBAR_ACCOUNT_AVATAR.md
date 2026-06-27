# TopBar Account Avatar

## 06/27:'Use account avatar beside username'

### Scope

The top account button now renders the signed-in user's `avatar_url` beside the username. The previous decorative ring has been replaced by a real circular avatar.

### Usage

- `Dashboard.tsx` passes `authSession.user.avatar_url` into `TopBar` as `accountAvatarUrl`.
- `TopBar.tsx` renders an image when `accountAvatarUrl` is present.
- If the image URL is empty or fails to load, the avatar falls back to the first character of the display name.
- `TopBar.css` keeps the avatar at `34px` by `34px` and crops images with `object-fit: cover`.

### Expected Output

```text
@username [round avatar] [chevron]
```

### Verification

```powershell
cd frontend
npm.cmd run build
```

The build must pass, and the account button should show the avatar image when `avatar_url` is available.

# Animal Gateway Branding Customization

This branch (`custom-branding-animal-gateway`) contains branding customizations for the Animal Gateway project.

## Changes Made

### UI Branding Updates

All user-facing "LiteLLM" references have been changed to "Animal Gateway":

1. **Page Title**: 
   - Changed from "LiteLLM Dashboard" to "Animal Gateway Dashboard"
   - File: `ui/litellm-dashboard/src/app/layout.tsx`

2. **Login Page**:
   - Brand icon changed from 🚅 to 🐾
   - Text updated from "LiteLLM" to "Animal Gateway"
   - File: `ui/litellm-dashboard/src/app/login/LoginPage.tsx`

3. **Onboarding Page**:
   - Brand icon changed from 🚅 to 🐾
   - File: `ui/litellm-dashboard/src/app/onboarding/page.tsx`

4. **MCP OAuth Callback Page**:
   - Updated page title and description
   - File: `ui/litellm-dashboard/src/app/mcp/oauth/callback/page.tsx`

## Modified Files

```
ui/litellm-dashboard/src/app/layout.tsx
ui/litellm-dashboard/src/app/login/LoginPage.tsx
ui/litellm-dashboard/src/app/onboarding/page.tsx
ui/litellm-dashboard/src/app/mcp/oauth/callback/page.tsx
```

## Building Docker Image

To build a custom Docker image with these branding changes:

```bash
# From the litellm repository root
docker build -t animal-gateway/litellm:custom .

# Or with a specific tag
docker build -t animal-gateway/litellm:v1.0.0 .
```

## Using the Custom Image

Update your `docker-compose.yml` to use the custom image:

```yaml
services:
  litellm:
    # Use custom image instead of official
    image: animal-gateway/litellm:custom
    # ... rest of configuration
```

## Syncing with Upstream

To keep this branch updated with the latest LiteLLM changes:

```bash
# Add upstream remote (if not already added)
git remote add upstream https://github.com/BerriAI/litellm.git

# Fetch upstream changes
git fetch upstream

# Merge upstream main into your branch
git checkout custom-branding-animal-gateway
git merge upstream/main

# Resolve conflicts if any
# ... resolve conflicts in the 4 modified files ...

# Push updated branch
git push origin custom-branding-animal-gateway
```

## Future Customizations

Additional branding elements that could be customized:

- [ ] Favicon (`ui/litellm-dashboard/public/favicon.ico`)
- [ ] Logo images
- [ ] Color theme (Tailwind/CSS)
- [ ] Footer text
- [ ] Navigation bar branding
- [ ] Documentation links

## Related Documentation

See the main Animal Gateway project for deployment guides:
- `~/workspace/xykong/animal-gateway/deploy/CUSTOM-BUILD-GUIDE.md`
- `~/workspace/xykong/animal-gateway/deploy/ADMIN-UI-CUSTOMIZATION.md`

## Commit History

- `b9781481a5` - feat: 更新品牌为 Animal Gateway

---

**Maintained by**: xykong
**Branch**: custom-branding-animal-gateway
**Base**: BerriAI/litellm main branch

# 🔧 Google Drive & Calendar Integration for Inanis Garage

## 🌟 Why Add Google Integration?

- **FREE 15GB storage** for all vehicle documents
- **Unlimited calendar events** for driver assignments
- **Automatic cloud backup** of important files
- **Easy document sharing** with your team
- **Professional document management**

**Note: Inanis Garage works perfectly WITHOUT Google - this just adds cloud features!**

## 📋 Complete Setup Guide (15 minutes)

### Step 1: Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"New Project"** (top-left dropdown)
3. Project name: `Inanis Garage Cloud`
4. Click **"CREATE"**
5. Wait for project creation (30 seconds)

### Step 2: Enable Required APIs
1. In search bar: **`Google Drive API`**
2. Click result → Press **"ENABLE"**
3. In search bar: **`Google Calendar API`**
4. Click result → Press **"ENABLE"**

✅ Both should show "API enabled"

### Step 3: Create Service Account
1. Navigate: **IAM & Admin** → **Service Accounts**
2. Click **"+ CREATE SERVICE ACCOUNT"**
3. **Name:** `inanis-garage-service`
4. **Description:** `Service account for Inanis Garage system`
5. Click **"CREATE AND CONTINUE"**
6. **Skip role assignment** → **"CONTINUE"**  
7. **Skip user access** → **"DONE"**

### Step 4: Generate Credentials
1. Click your service account: `inanis-garage-service@...`
2. Go to **"KEYS"** tab
3. **"ADD KEY"** → **"Create new key"**
4. Select **"JSON"** format
5. Click **"CREATE"**
6. **File downloads** automatically
7. **Rename to:** `credentials.json`
8. **Move to** Inanis Garage directory

### Step 5: Test Integration
1. **Restart Inanis Garage:**
   ```bash
   ./quick-start.sh
   ```
2. **Login:** admin / adminpass
3. **Add vehicle** (if none exist)
4. **Upload document:**
   - Should appear in Google Drive
   - Success message shown
5. **Assign driver:**
   - Should create calendar event
   - Check your Google Calendar

## ✅ Verification Checklist

- [ ] Google Cloud project created
- [ ] Drive API enabled
- [ ] Calendar API enabled  
- [ ] Service account created
- [ ] `credentials.json` downloaded & placed
- [ ] Inanis Garage restarted
- [ ] Document upload successful
- [ ] Calendar event created

## 🔧 Troubleshooting

### "Google services not available"
**Solutions:**
1. Verify `credentials.json` exists in correct location
2. Check file is valid JSON (can open in text editor)
3. Confirm both APIs are enabled
4. Restart Inanis Garage application

### "Document upload failed"
**Solutions:**
1. Check internet connection
2. Verify `credentials.json` permissions
3. Review Inanis Garage logs:
   ```bash
   docker-compose logs inanis-garage
   # or
   tail -f logs/flask_app.log
   ```

### "Calendar event creation failed"
**Solutions:**
1. Ensure Calendar API is enabled
2. Check service account permissions
3. Verify calendar sharing settings

### Permission denied errors
**Fix file permissions:**
```bash
chmod 644 credentials.json
chmod +x quick-start.sh
```

## 💡 Pro Tips

### Security Best Practices
- **Never commit** `credentials.json` to version control
- **Add to .gitignore:** `credentials.json`
- **Store securely** and backup credentials
- **Monitor usage** in Google Cloud Console
- **Rotate annually** for enhanced security

### Organization Tips
- **Create folders** in Google Drive for each vehicle
- **Naming convention:** `VEHICLE_TYPE_DATE.pdf`
- **Set reminders** for document expiry
- **Share folders** with team members appropriately

## 🆓 Free Usage Limits

| Google Service | Free Limit | Perfect For |
|---------------|------------|-------------|
| **Drive API** | 1,000 requests/100 seconds | Small-medium garages |
| **Drive Storage** | 15GB | Thousands of documents |
| **Calendar API** | Unlimited | No restrictions |
| **Service Account** | Unlimited | No monthly fees |

**Ideal for garages with up to 50-100 vehicles!**

## 🆘 Still Need Help?

### Check Application Logs
```bash
# Docker deployment
docker-compose logs -f inanis-garage

# Python deployment
tail -f logs/flask_app.log
```

### Verify Setup
1. **File exists:** `ls -la credentials.json`
2. **Valid JSON:** `python -m json.tool credentials.json`
3. **Correct location:** Same directory as `app.py`
4. **APIs enabled:** Check Google Cloud Console quotas

### Reset and Retry
1. **Delete service account** in Google Cloud Console
2. **Create new service account** with same steps
3. **Download fresh credentials**
4. **Replace old credentials.json**
5. **Restart Inanis Garage**

## 🎉 Success Indicators

Once working properly, you'll have:
- ✅ **Automatic document backup** to Google Drive
- ✅ **Calendar integration** for driver assignments
- ✅ **15GB free cloud storage**
- ✅ **Professional document management**
- ✅ **Team collaboration** capabilities
- ✅ **Cross-device sync** for all data

## 📈 Advanced Features

With Google integration enabled:
- **Document sharing** via Google Drive links
- **Calendar notifications** for assignments
- **Mobile access** through Google apps
- **Team collaboration** on shared folders
- **Version history** for all documents
- **Advanced search** across all files

---

**Your Inanis Garage is now enterprise-ready with full cloud integration!** ☁️🔧

**Remember: The garage works great without Google too - this just adds professional cloud features!**

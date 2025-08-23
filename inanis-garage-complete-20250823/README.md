# 🔧 Inanis Garage Management System

**Professional automotive fleet management with Apple-inspired design**

![Inanis Garage](https://img.shields.io/badge/Inanis-Garage-007AFF?style=for-the-badge)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🚗 About Inanis Garage

**Inanis Garage** is a comprehensive fleet management system designed specifically for automotive workshops, garages, and fleet operators. Built with Apple's design philosophy, it combines professional functionality with an elegant, intuitive interface.

## ✨ Key Features

### 🍎 **Apple-Inspired Design**
- **Glassmorphism effects** with backdrop blur technology
- **Apple's signature color palette** (#007AFF) 
- **San Francisco font** family (-apple-system)
- **Smooth animations** and delightful micro-interactions
- **iOS-style interface** elements
- **Mobile-responsive** design

### 🔧 **Garage Management**
- **Vehicle Fleet Tracking** - Complete vehicle lifecycle management
- **Driver Assignment** - Assign vehicles to drivers with calendar sync
- **Fuel Efficiency Monitoring** - Track consumption and costs
- **Document Management** - Upload to Google Drive with expiry alerts
- **Maintenance Records** - Service history and scheduling
- **Comprehensive Reports** - Fleet insights and analytics
- **Multi-user Access** - Role-based permissions (Admin/Driver)

### 🛡️ **Enterprise Security**
- **CSRF protection** on all forms
- **Secure sessions** with auto-expiry
- **Input validation** and sanitization
- **Admin access controls**
- **Comprehensive logging**
- **Data persistence** with backups

### ☁️ **Google Integration** 
- **Google Drive Storage** - 15GB FREE document storage
- **Google Calendar Sync** - Automatic assignment events
- **Offline Capability** - Works without Google services
- **Enterprise-grade** error handling

## 🚀 Quick Start

### One-Click Deployment (Recommended)
```bash
# Make executable and run
chmod +x quick-start.sh
./quick-start.sh
```

### Docker Deployment
```bash
# Deploy with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f inanis-garage
```

### Manual Python Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Create directories
mkdir -p data temp_uploads logs static/css templates

# Start Inanis Garage
python app.py
```

## 🌐 Access Your System

- **URL:** http://localhost:5000
- **Login:** admin / adminpass
- **⚠️ Security:** Change password after first login!

## 💰 Cost Breakdown (100% FREE!)

| Component | Monthly Cost | Details |
|-----------|-------------|---------|
| **Inanis Garage** | **$0** | Open source software |
| **Google Drive** | **$0** | 15GB free storage |
| **Google Calendar** | **$0** | Unlimited events |
| **Self-hosting** | **$0** | Your own server |
| **Cloud hosting** | **$0-$5** | Free tiers available |

**Total: $0 - $5/month**

## 📁 File Structure

```
inanis-garage/
├── app.py                    # Main Flask application
├── requirements.txt          # Python dependencies
├── Dockerfile               # Container configuration
├── docker-compose.yml       # Multi-container setup
├── quick-start.sh           # One-click deployment
├── README.md                # This documentation
├── static/css/
│   └── apple-style.css      # Apple design system
├── templates/
│   ├── index.html           # Garage dashboard
│   ├── login.html           # Login interface
│   ├── add_vehicle.html     # Vehicle management
│   └── ...                  # Additional templates
├── data/                    # Application data (auto-created)
├── logs/                    # System logs (auto-created)
└── temp_uploads/            # File uploads (auto-created)
```

## 🔧 Google Drive Setup (Optional)

**Inanis Garage works perfectly without Google - this adds cloud features!**

### Quick Setup (15 minutes)
1. **Google Cloud Console** → Create project "Inanis Garage"
2. **Enable APIs** → Google Drive API + Google Calendar API
3. **Service Account** → Create "inanis-garage-service"
4. **Download JSON** → Rename to `credentials.json`
5. **Place File** → In Inanis Garage directory
6. **Restart App** → Google features will be enabled

**Benefits:**
- 📁 **Document backup** to Google Drive
- 📅 **Calendar integration** for assignments
- 🔄 **Automatic sync** across devices
- 👥 **Team collaboration** features

## 🛠️ Management Commands

### Docker Deployment
```bash
# View Inanis Garage logs
docker-compose logs -f inanis-garage

# Stop the system
docker-compose down

# Restart services
docker-compose restart inanis-garage

# Update system
git pull && docker-compose up -d --build

# Backup data
tar -czf inanis-backup-$(date +%Y%m%d).tar.gz data/
```

### Python Deployment
```bash
# View logs
tail -f logs/flask_app.log

# Stop application
pkill -f app.py

# Restart Inanis Garage
python app.py

# Check status
ps aux | grep app.py
```

## 📊 Dashboard Features

### Fleet Overview
- **Real-time vehicle status** with visual indicators
- **Availability tracking** and assignment monitoring
- **Document expiry alerts** for compliance
- **Quick action buttons** for common tasks

### Vehicle Management
- **Apple-styled forms** for adding/editing vehicles
- **Odometer tracking** with fuel efficiency
- **Service history** and maintenance records
- **Photo and document** attachment

### Analytics & Reports
- **Fuel efficiency trends** with charts
- **Vehicle utilization** optimization
- **Cost analysis** and budget tracking
- **Maintenance scheduling** alerts

## 🔒 Security Features

- **CSRF Protection** - All forms secured
- **Rate Limiting** - 5 login attempts/minute
- **Secure Sessions** - 2-hour auto-expiry
- **Input Validation** - XSS prevention
- **File Upload Security** - Type and size limits
- **Admin Controls** - Restricted operations
- **Audit Logging** - Complete activity tracking

## 📱 Mobile Support

- **Responsive Design** - Works on all devices
- **Touch Optimized** - iOS-style interactions
- **Fast Performance** - Optimized loading
- **Offline Capable** - Core features work offline
- **Apple Device Ready** - Perfect on iPhone/iPad

## 🚀 Deployment Options

### Free Hosting
- **Self-hosting** - Your computer/server (FREE)
- **Railway.app** - Free tier with auto-deploy
- **Render.com** - Free tier with SSL
- **Google Cloud Run** - 2M requests/month free
- **Heroku** - Container deployments

### Professional Hosting
- **DigitalOcean** - $5/month droplets
- **AWS/Azure** - Pay-as-you-scale
- **Google Cloud** - Enterprise infrastructure

## 🔧 Troubleshooting

### Common Issues
```bash
# Check Inanis Garage status
docker-compose ps

# View detailed logs
docker-compose logs --tail=50 inanis-garage

# Restart services
docker-compose restart

# Rebuild containers
docker-compose down && docker-compose up -d --build
```

### Google Integration Issues
1. **Verify credentials.json** exists and is valid JSON
2. **Check API enablement** in Google Cloud Console
3. **Test permissions** - service account access
4. **Review logs** for specific error messages

## 🎨 Customization

### Branding
- Update company name in templates
- Modify colors in `apple-style.css`
- Replace logo/favicon files
- Customize dashboard layout

### Features
- Add custom vehicle fields
- Extend reporting capabilities
- Integrate additional APIs
- Create custom workflows

## 🤝 Support

- **Documentation** - Complete guides included
- **Self-hosted** - Full data control
- **Open Source** - MIT License
- **Community** - GitHub issues and discussions

## 🏆 What Makes Inanis Garage Special

### Professional Quality
- **Apple-grade UI/UX** with attention to detail
- **Enterprise security** following best practices
- **Production-ready** with Docker deployment
- **Scalable architecture** for growing businesses

### Garage-Specific Features
- **Vehicle lifecycle** management from purchase to disposal
- **Driver certification** tracking with document storage
- **Fuel cost optimization** with efficiency monitoring
- **Maintenance scheduling** with automated reminders
- **Multi-location** support for garage chains
- **Compliance tracking** for regulatory requirements

### Technology Excellence
- **Modern Python** with Flask framework
- **Responsive design** with Bootstrap 5
- **Secure implementation** with CSRF protection
- **Cloud integration** with Google services
- **Container deployment** with Docker
- **Comprehensive logging** for monitoring

---

## 🏁 Ready to Start?

1. **Deploy**: `chmod +x quick-start.sh && ./quick-start.sh`
2. **Access**: http://localhost:5000
3. **Login**: admin / adminpass
4. **Manage**: Add vehicles, assign drivers, track everything!

**🔧 Welcome to Inanis Garage - Where automotive management meets Apple elegance! 🚗**

---

### 📞 Support & Community

- **GitHub**: Report issues and contribute
- **Documentation**: Complete setup guides
- **License**: MIT - Free for commercial use

**Built with ❤️ for automotive professionals who demand excellence.**

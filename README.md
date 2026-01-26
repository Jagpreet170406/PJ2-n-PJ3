Installing VENV Instructions:
1. Open Command Prompt
2. Type: python -m venv venv
3. Type the following:
 cd venv 
 cd Scripts
 .\activate
 cd.. 
 cd..
4. Install the Required Dependencies: pip install blinker==1.9.0 certifi==2026.1.4 charset-normalizer==3.4.4 click==8.3.1 colorama==0.4.6 et_xmlfile==2.0.0 Flask==3.1.2 Flask-WTF==1.2.2 greenlet==3.3.0 idna==3.11 itsdangerous==2.2.0 Jinja2==3.1.6 MarkupSafe==3.0.3 numpy==2.4.1 openpyxl==3.1.5 pandas==2.3.3 python-dateutil==2.9.0.post0 pytz==2025.2 requests==2.32.5 six==1.17.0 SQLAlchemy==2.0.45 typing_extensions==4.15.0 tzdata==2025.3 urllib3==2.6.3 Werkzeug==3.1.5 WTForms==3.2.1 xlrd==2.0.2
5. Once Installed, DO NOT COMMIT CHANGES!
6. Proceed with the following:
In Source Control, Click the "Tilted-U" arrow to Discard ALL CHANGES. (This is to prevent the venv from being uploaded to the repository)
7. Then you can commit your own changes in your own files. 


Pushover to PJ3 (Final Presentation):
1. real_time_analytics WILL BE CHANGED to inventory_analysis (since the recommendations are already INSIDE market_analysis)
2. manage_users.html (RBAC has issues - need to fix the employee/admin/superowner roles)
superowner: can do everything 
admin: basically has same rights as superowner JUST THAT they can add new employees into the RBAC.
employee: Limited access. Only to Home & Inventory (Updation of Inventory Only) - On the Ground Employees
3. images in cart.html and inventory.html - placeholder images will be replaced with actual product images. Just need to ensure images are manually searched. (May or May Not Use AI Image Generation)
4. Inventory (Changed to a Dropdown Menu consisting of Inventory & Stock Take [Currently as inventory.html] and Inventory Analysis [currently real_time_analytics.html] - real_time_analytics.html NOT functional yet)
5. Contact Us Page - (fill in credentials - sync w database and see it on staff side)
6. Orders Page in Staff Side (NOT FUNCTIONAL YET - Not created yet and must be sync w database and cart)
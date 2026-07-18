# dashboard/public/

Place founder photo here as `founder.jpg` (any size, ~600×800 portrait works).
If prabhat.jpg is missing, the marketing site shows a `founder.jpg` link that will 404.

To use your photo:
```bash
cp /path/to/prabhat.jpg /Users/prabhatranjan/Business/crewcircle/localmate/dashboard/public/founder.jpg
```

Then redeploy:
```bash
cd /Users/prabhatranjan/Business/crewcircle/localmate/dashboard
vercel deploy --prebuilt --prod --yes
```

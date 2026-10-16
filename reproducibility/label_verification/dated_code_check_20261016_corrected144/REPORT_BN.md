# তোমার দেওয়া label: code দিয়ে নতুন যাচাই

সর্বশেষ dated CSV/Backup-এর **694টি উত্তর**, **245টি জায়গা** ধরে আগের frozen code আবার চালানো হয়েছে। PNG-এর রং গুনে নয়; আসল Sentinel-2 DN band, product XML calibration এবং quality mask ব্যবহার করা হয়েছে।

- 🟢 **212টি** তারিখে তোমার binary উত্তর ও কোড মিলে।
- 🔴 **0টি** তারিখে মতপার্থক্য আছে; কার উত্তর ভুল তা এই তুলনা একা বলে না।
- 🟡 **454টি** binary human উত্তরের ক্ষেত্রে কোড নির্ভরযোগ্য binary rule label দেয়নি। এগুলো human ভুল হিসেবে চিহ্নিত হয়নি।
- ⚪ **28টি** তোমার অনিশ্চিত উত্তর অনিশ্চিতই রাখা হয়েছে।

কোড binary label দেওয়া 212টি তারিখের মধ্যে 212টি মিলে। **এটি independent accuracy নয় এবং পুরো ৬৯৪টির সঠিকতার শতাংশ নয়।**

কোড সিদ্ধান্ত দিতে পারেনি এমন 454টি তারিখে তোমার existing dated answer রাখা আছে: **313টি পানি আছে, 141টি পানি নেই**। এগুলো human-assisted answer; code-confirmed truth নয়। ভিন্ন দিনের উত্তর আলাদা থাকলে whole-month সিদ্ধান্ত জোর করে বানানো হয় না।

এই input version-এ code-এর ফল জানার পরে ব্যবহারকারীর নির্দেশে সংশোধিত dated answer আছে: **1টি**। তাই post-correction agreement-কে blind validation বলা যাবে না।

## যে তারিখে মতপার্থক্য

| নমুনা | জেলা | আসল ছবির তারিখ | তোমার উত্তর | কোডের উত্তর | সিদ্ধান্ত |
|---|---|---|---|---|---|

**35টি জায়গায় তারিখভেদে 0/1 আলাদা**, এবং **19টি জায়গায় অন্তত একটি অনিশ্চিত দিন** আছে। সংখ্যা দুটি overlap করতে পারে। তারিখের পরিবর্তনকে ভুল, কিংবা drought recovery-এর প্রমাণ বলা হয়নি।

**তোমার কোনো label, reviewer, review time বা final research result পরিবর্তন করা হয়নি।** কোডের এই পরীক্ষার জন্য নতুন manual কাজ দেওয়া হচ্ছে না।

[রঙসহ বিস্তারিত দেখো](CHECK_REPORT.html)। সব ৬৯৪টি date-wise comparison: `all_694_date_comparisons.json`; source hashes ও সীমা: `CHECK_RESULT.json`।

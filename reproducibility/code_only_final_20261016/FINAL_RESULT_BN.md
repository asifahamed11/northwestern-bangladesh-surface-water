# কোড দিয়ে চূড়ান্ত বিশ্লেষণ: সহজ ফল

**এই নির্ধারিত scope-এ paper লেখা শুরু করা যাবে। নতুন manual label বা নতুন download এখন প্রয়োজন নেই।** এটি সীমিত ফল নিয়ে লেখার অনুমতি-সংক্রান্ত workflow সিদ্ধান্ত; submission বা publication readiness-এর সনদ নয়।

শিরোনাম: **Climate-adjusted surface-water changes and observation uncertainty in northwestern Bangladesh**

## কী পাওয়া গেছে

১. ২০০০–২০২১-এর একই 1276.41 km² common-observation footprint-এ seasonal source-class এলাকা 938.53 থেকে 699.91 km² হয়েছে: **25.42% কম**। এটি পুরো তিন জেলার সব পানির error-adjusted হিসাব নয়।

২. নওগাঁ ও রাজশাহীর seasonal-class-এর negative time association climate, observation effort ও ২০১৬ processing-boundary sensitivity-তেও থাকে। তবে seasonal climate models-এর mean fold RMSE চারটি region/union summary-তেই training-mean baseline-এর চেয়ে খারাপ। তাই model-কে ভালো forecasting system বা মানুষের কাজের causal প্রমাণ বলা যাবে না।

৩. Permanent source-class-এর দুই endpoint-এর পার্থক্য +41.04% হলেও processing-boundary sensitivity-এর পরে নিয়মিত বৃদ্ধির পরিষ্কার প্রমাণ নেই। এটি স্থায়ী পানির নিশ্চিত বৃদ্ধি হিসেবে paper-এর headline হবে না।

৪. ২০১৫–২০২৪-এর আলাদা radar cohort-এ রাজশাহীর seasonal-envelope endpoint-এর positive association আছে। এটি annual JRC seasonal decline-কে বাতিল করে না: period, footprint, sensor ও measured quantity আলাদা। সব district, cohort ও threshold-এর ফল রাখা হয়েছে।

## আগের manual কাজ কী হলো

তোমার **২৪৫টি জায়গার ৬৯৪টি dated answer সম্পূর্ণ** আছে। 430টি পানি, 236টি পানি নেই, 28টি অনিশ্চিত। একই তারিখের উত্তর অন্য তারিখে কপি করা হয়নি।

পুরো ৭২০টি sample-এর মধ্যে **337টি automatic proxy + 194টি consistent assisted interpretation = 531টি assigned sample**। বাকি **189টি** অনির্ধারিত: 138টির পর্যাপ্ত dated support নেই, 35টির বিভিন্ন তারিখের উত্তর আলাদা, 16টির উত্তর অনিশ্চিত। অনির্ধারিতগুলোকে শুকনা জমি বানানো হয়নি।

Sampling weights ধরলে assigned comparison চারটি নির্ধারিত মাসের frame-এর **76.54%**। ওই assigned অংশে JRC/proxy label agreement **98.56%**। এই সংখ্যা independent accuracy নয়। সব unknown comparison weight রাখলে binary-completion agreement range **75.44–98.90%**; এটি physical-water accuracy interval নয়।

Automatic-only subset-এ সব assigned label JRC-এর সঙ্গে মিলে গেলেও সেটি সীমিত selected support। Empirical bootstrap-এ variation না থাকলে [100,100] confidence বলে দেখাইনি; interval unavailable ও degenerate flag রাখা হয়েছে। ২০০০ bootstrap-এ pixel–month-ই unit, ছবির তারিখ নয়।

## খরার পরে পানি ফেরার সময়

**নির্ভরযোগ্য সময় পাওয়া যায়নি।** ১০৮টি primary event–cohort record এবং ৯টি sensitivity specification-এর সব duration খালি আছে। অর্থ পানি ফেরেনি নয়। বর্তমান paper-এ এই observation limitation থাকবে, recovery-time estimate বা causal recovery claim থাকবে না।

## যাচাই ও ফাইল

9393টি declared source/evidence file-এর hash মিলেছে। নতুন ১,৪৪০ export row থেকে ৫,৭৬০ threshold row আবার হিসাব করে আগের ফল মিলেছে। 149টি Python test ও 9টি Node test pass; এগুলো software checks, ground truth নয়। ১২টি figure-এর contact sheet ও নতুন figure দেখা হয়েছে। Original labels, source data ও পূর্বের protocol সংরক্ষিত; ব্যবহারকারীর নির্দেশের সংশোধন থাকলে তা আলাদা version-এ আছে।

Methods-এর bounded research note: [METHOD_RESEARCH.md](METHOD_RESEARCH.md)। পদ্ধতিগত article-এ [Olofsson et al. 2014](https://doi.org/10.1016/j.rse.2014.02.015), [Brown et al. 2022](https://doi.org/10.1038/s41597-022-01307-4) এবং প্রাসঙ্গিক [Saunders et al. 2025](https://doi.org/10.1029/2025EF005966) ব্যবহৃত হয়েছে। এগুলো স্থানীয় accuracy সংখ্যা দেয়নি। Metadata/source access ও claim locators `research/`-এ; ব্যবহৃত procedural skill-এর software acknowledgement-ও সেখানে রাখা হয়েছে।

লেখার পরিকল্পনা ও কোন দাবি ব্যবহার করা যাবে: [PAPER_HANDOFF.md](PAPER_HANDOFF.md)। সব numerical result: `analysis_v3_user_label144/RESULTS.json`; Tables ও Figures একই directory-তে। কোনো target journal, novelty priority বা acceptance guarantee পরীক্ষা করা হয়নি।

## ব্যবহারকারীর নির্দেশের সংশোধন

নমুনা ১৪৪-এর ২০২৩-০৩-৩০ তারিখের উত্তর 0 থেকে 1 হয়েছে। এটি code-এর ফল জানার পরে ব্যবহারকারীর explicit correction; নতুন independent image verification নয়। Original CSV ও Backup অক্ষত। কোডের undecided ৪৫৪টি তারিখে existing human answer-ই আছে: ৩১৩টি পানি, ১৪১টি পানি নেই; code ওই label-গুলোকে স্বাধীনভাবে নিশ্চিত করেনি।

# Accuracy results

- Expected rule retrieved (top 8+): 23/23 (100%)
- Expected rule cited in the answer: 23/23 (100%)
- Right table value in the answer (Rule 56 front open space): 8/8 (100%)
- Quoted lines found in the rule text: 85/87 (4 matched only as flattened table text)
- Not-found on out-of-scope questions: 2/2 (100%)
- Errors: 0

| Case | Question | Result | Note |
|---|---|---|---|
| Q1 | My house faces a 10 m wide street and will be 9 m tall. How much open  | retrieved=Y cited=Y |  |
| Q2 | I want a farm house on agricultural land. What is the minimum plot siz | retrieved=Y cited=Y |  |
| Q3 | My development permission was granted in 2023. How long does it stay v | retrieved=Y cited=Y |  |
| Q4 | I applied for building permission and the authority has not replied. W | retrieved=Y cited=Y |  |
| Q5 | How far must my balcony stay from a low-voltage overhead electric line | retrieved=Y cited=Y | 1 quote(s) not matched |
| Q6 | Who is allowed to sign and submit my building plans? | retrieved=Y cited=Y |  |
| Q7 | What documents go with an application for building permission? | retrieved=Y cited=Y |  |
| Q8 | What is the fee for building permission for a residential house? | retrieved=Y cited=Y | 1 quote(s) not matched |
| Q9 | Can I change my plan after it is sanctioned? | retrieved=Y cited=Y |  |
| Q10 | What is the minimum rear open space for a 150 sq m residential plot? | retrieved=Y cited=Y |  |
| Q11 | Do I need separate development permission for a 300 sq m plot that mat | retrieved=Y cited=Y |  |
| Q12 | Which rule decides what happens when the Development Plan and these ru | retrieved=Y cited=Y |  |
| Q13 | What are the rules for lifts in a building taller than 15 m? | retrieved=Y cited=Y |  |
| Q14 | मेरा प्लॉट 200 वर्ग मीटर का है और सामने 9 मीटर चौड़ी सड़क है। आगे कितन | retrieved=Y cited=Y |  |
| Q15 | बिल्डिंग परमिशन की फीस कितनी है और किस नियम में लिखी है? | retrieved=Y cited=Y |  |
| Q16 | How do I pay my property tax online? | NOT_FOUND expected | OK |
| Q17 | What is the current market rate for land in Kolar Road, Bhopal? | NOT_FOUND expected | OK |
| T1 | My house is 9 m tall and faces an 8 m wide street. How much front open | retrieved=Y cited=Y | value 3.0: OK (also mentions ['6.0']) |
| T2 | My house is 9 m tall and faces a 9 m wide street. How much front open  | retrieved=Y cited=Y | value 3.0: OK (also mentions ['3.6', '6.0']) |
| T3 | My house is 9 m tall and faces a 10 m wide street. How much front open | retrieved=Y cited=Y | value 3.6: OK (also mentions ['6.0']) |
| T4 | My house is 9 m tall and faces a 12 m wide street. How much front open | retrieved=Y cited=Y | value 3.6: OK (also mentions ['4.5']) |
| T5 | My house is 9 m tall and faces a 15 m wide street. How much front open | retrieved=Y cited=Y | value 4.5: OK (also mentions ['6.0']) |
| T6 | My house is 9 m tall and faces a 20 m wide street. How much front open | retrieved=Y cited=Y | value 6.0: OK |
| T7 | मेरा मकान 9 मीटर ऊँचा है और सामने 15 मीटर चौड़ी सड़क है। आगे कितनी जगह | retrieved=Y cited=Y | value 4.5: OK |
| T8 | mera ghar 9 m ooncha hai aur saamne 20 m chaudi sadak hai, aage kitni  | retrieved=Y cited=Y | value 6.0: OK |

## To check by hand
- Q5: quote not found in rule text: 'Low and Medium voltage lines and service lines 2.5 1.2'
- Q8: quote not found in rule text: 'A building intended to be used exclusively for residence. Rs. 10.00 per square meter of the built up area.'

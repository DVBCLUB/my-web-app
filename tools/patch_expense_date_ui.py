from pathlib import Path

path = Path('PythonApplication1/web_app.py')
text = path.read_text(encoding='utf-8')

old_input = '<label>Ngày chi<input name="expense_date" type="date"></label>'
new_input = '<label>Ngày chi<input name="expense_date" type="text" inputmode="numeric" maxlength="10" placeholder="DD/MM/YYYY" pattern="\\\\d{2}/\\\\d{2}/\\\\d{4}" autocomplete="off"></label>'
text = text.replace(old_input, new_input)

anchor = "const localIsoMonth=()=>localIsoDate().slice(0,7);"
helpers = """const localIsoMonth=()=>localIsoDate().slice(0,7);
    const toDisplayDate=v=>{if(!v)return'';const s=String(v).slice(0,10);if(/^\\d{4}-\\d{2}-\\d{2}$/.test(s)){const [y,m,d]=s.split('-');return `${d}/${m}/${y}`}return s};
    const toIsoDate=v=>{const s=String(v||'').trim();if(!s)return localIsoDate();const m=s.match(/^(\\d{2})\\/(\\d{2})\\/(\\d{4})$/);if(m)return `${m[3]}-${m[2]}-${m[1]}`;return s};
    const bindDateMask=el=>el&&el.addEventListener('input',()=>{let v=el.value.replace(/\\D/g,'').slice(0,8);if(v.length>=5)v=`${v.slice(0,2)}/${v.slice(2,4)}/${v.slice(4)}`;else if(v.length>=3)v=`${v.slice(0,2)}/${v.slice(2)}`;el.value=v});"""
if helpers not in text:
    text = text.replace(anchor, helpers)

# Display dates in expense approval and expense list renderers.
text = text.replace('${esc(e.expense_date)}</td><td>${esc(e.project_code)}', '${esc(toDisplayDate(e.expense_date))}</td><td>${esc(e.project_code)}')
text = text.replace('${esc(e.expense_date)}</td><td>${esc(e.project_name)}', '${esc(toDisplayDate(e.expense_date))}</td><td>${esc(e.project_name)}')

# Convert the expense form date from DD/MM/YYYY to ISO before sending to API.
submit_old = "expenseForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(expenseForm).entries());"
submit_new = "expenseForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(expenseForm).entries());data.expense_date=toIsoDate(data.expense_date);"
text = text.replace(submit_old, submit_new)

# Set default display date and bind the mask at boot/event binding time.
bind_anchor = "backupBtn.addEventListener('click',async()=>"
bind_code = "if(expenseForm&&expenseForm.expense_date){expenseForm.expense_date.value=toDisplayDate(localIsoDate());bindDateMask(expenseForm.expense_date)};\n    backupBtn.addEventListener('click',async()=>"
if "bindDateMask(expenseForm.expense_date)" not in text:
    text = text.replace(bind_anchor, bind_code)

path.write_text(text, encoding='utf-8')

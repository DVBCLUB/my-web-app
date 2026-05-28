from pathlib import Path

path = Path('PythonApplication1/web_app.py')
text = path.read_text(encoding='utf-8')

# 1) API endpoint for construction accounting rules.
api_anchor = '\n\n    @app.get("/healthz")'
api_block = '''

    @app.get("/api/construction-accounting/rules")
    @api_error
    def construction_accounting_rules():
        rules_path = Path(__file__).resolve().parent / "data" / "construction_accounting_rules.json"
        if not rules_path.exists():
            return jsonify({"version": "missing", "cost_groups": [], "reports": []})
        return jsonify(json.loads(rules_path.read_text(encoding="utf-8")))
'''
if '/api/construction-accounting/rules' not in text and api_anchor in text:
    text = text.replace(api_anchor, api_block + api_anchor, 1)

# 2) Add UI card below expense quick-entry form.
form_anchor = '''            <div class="wide actions"><button class="primary" type="submit">Lưu chi phí</button><button class="secondary" type="reset">Xóa form</button></div>
          </form>
        </div>
        <div class="grid kpis">'''
rule_card = '''            <div class="wide actions"><button class="primary" type="submit">Lưu chi phí</button><button class="secondary" type="reset">Xóa form</button></div>
          </form>
        </div>
        <div class="card" id="constructionRuleCard">
          <div class="toolbar"><h3>Checklist chứng từ & hạch toán xây dựng</h3><select id="ruleGroupSelect"></select></div>
          <div class="grid two">
            <div>
              <p class="section-kicker" id="ruleCode">Nhóm chi phí</p>
              <h3 id="ruleName">Chọn danh mục chi phí để xem gợi ý</h3>
              <p class="muted" id="ruleAccounts">Tài khoản gợi ý sẽ hiện tại đây.</p>
              <h3>Chứng từ cần có</h3>
              <ul id="ruleDocs" class="muted"></ul>
            </div>
            <div>
              <h3>Cảnh báo thuế/kế toán</h3>
              <ul id="ruleWarnings" class="muted"></ul>
              <h3>Kiểm soát nên bật</h3>
              <ul id="ruleControls" class="muted"></ul>
            </div>
          </div>
        </div>
        <div class="grid kpis">'''
if 'id="constructionRuleCard"' not in text and form_anchor in text:
    text = text.replace(form_anchor, rule_card, 1)

# 3) Extend client-side state and loader.
text = text.replace('settings:null};', 'settings:null,constructionRules:null};')
text = text.replace('loadSettings(),loadUsers()])', 'loadSettings(),loadUsers(),loadConstructionAccountingRules()])')
loader_anchor = "    async function loadExpenses(){state.expenses=await api('/api/expenses');renderExpenses()}"
loader_block = """    async function loadExpenses(){state.expenses=await api('/api/expenses');renderExpenses()}
    async function loadConstructionAccountingRules(){try{state.constructionRules=await api('/api/construction-accounting/rules');renderConstructionAccountingRules()}catch(err){console.warn('Không tải được quy tắc kế toán xây dựng',err)}}"""
if 'loadConstructionAccountingRules' not in text and loader_anchor in text:
    text = text.replace(loader_anchor, loader_block, 1)

# 4) Render helper for the checklist card.
render_anchor = "    function renderLowStock(rows=[])"
render_block = r'''    function inferRuleCode(){
      if(ruleGroupSelect&&ruleGroupSelect.value)return ruleGroupSelect.value;
      const txt=`${expenseCategory?.selectedOptions?.[0]?.textContent||''}`.toLowerCase();
      if(/thầu|thau|sub/.test(txt))return 'SUBCONTRACTOR';
      if(/máy|may|dầu|dau|nhiên liệu|nhien lieu|ca máy|ca may/.test(txt))return 'MACHINE';
      if(/nhân công|nhan cong|lương|luong|khoán|khoan/.test(txt))return 'LABOR';
      if(/vật tư|vat tu|vật liệu|vat lieu|thép|thep|xi măng|xi mang|cát|cat|đá|da/.test(txt))return 'MATERIALS';
      if(/chung|quản lý|quan ly|văn phòng|van phong|công trường|cong truong/.test(txt))return 'OVERHEAD';
      return 'MATERIALS';
    }
    function listHtml(items=[]){return items.map(x=>`<li>${esc(x)}</li>`).join('')||'<li>Chưa có checklist.</li>'}
    function renderConstructionAccountingRules(){
      if(!document.getElementById('constructionRuleCard'))return;
      const groups=(state.constructionRules||{}).cost_groups||[];
      if(!groups.length){ruleName.textContent='Chưa có bộ quy tắc';return}
      if(ruleGroupSelect&&!ruleGroupSelect.options.length){ruleGroupSelect.innerHTML=groups.map(g=>`<option value="${esc(g.code)}">${esc(g.name)}</option>`).join('')}
      const code=inferRuleCode();
      const rule=groups.find(g=>g.code===code)||groups[0];
      if(ruleGroupSelect)ruleGroupSelect.value=rule.code;
      ruleCode.textContent=rule.code;
      ruleName.textContent=rule.name;
      const acc=rule.accounting_accounts||{};
      ruleAccounts.textContent=`Nợ: ${(acc.debit||[]).join(', ')} · Có: ${(acc.credit||[]).join(', ')}`;
      ruleDocs.innerHTML=listHtml(rule.required_documents||[]);
      ruleWarnings.innerHTML=listHtml(rule.tax_warnings||[]);
      ruleControls.innerHTML=listHtml(rule.suggested_controls||[]);
    }
'''
if 'function renderConstructionAccountingRules()' not in text and render_anchor in text:
    text = text.replace(render_anchor, render_block + render_anchor, 1)

# 5) Bind controls.
event_anchor = "    if(expenseForm&&expenseForm.expense_date){expenseForm.expense_date.value=toDisplayDate(localIsoDate());bindDateMask(expenseForm.expense_date)};"
event_block = """    if(expenseForm&&expenseForm.expense_date){expenseForm.expense_date.value=toDisplayDate(localIsoDate());bindDateMask(expenseForm.expense_date)};
    if(window.expenseCategory)expenseCategory.addEventListener('change',()=>{if(ruleGroupSelect)ruleGroupSelect.value='';renderConstructionAccountingRules()});
    if(window.ruleGroupSelect)ruleGroupSelect.addEventListener('change',renderConstructionAccountingRules);"""
if "ruleGroupSelect.addEventListener('change'" not in text and event_anchor in text:
    text = text.replace(event_anchor, event_block, 1)

path.write_text(text, encoding='utf-8')

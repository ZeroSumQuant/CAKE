# Claude Real-Time Interventions

## 🚨 STOP Patterns - Check These BEFORE Acting

### 1. Hidden Directory Detection
**BEFORE**: Using LS tool or bare `ls`  
**STOP**: LS tool doesn't show hidden files!  
**DO**: `ls -la` or `find . -name 'activate' -type f`

### 2. Script Execution
**BEFORE**: Running any script  
**STOP**: Check the interpreter first!  
**DO**: 
```bash
file <script>  # Check file type
head -1 <script>  # Check shebang
# Then use correct interpreter
```

### 3. Virtual Environment
**BEFORE**: Looking for venv  
**STOP**: It's hidden (starts with .)  
**DO**: `find /Users/dustinkirby -name "activate" -type f 2>/dev/null | grep -i cake`

### 4. Syntax Error Fixing
**BEFORE**: Creating fix scripts  
**STOP**: Don't fix one by one!  
**DO**:
1. Collect ALL errors first: `flake8 . --select E999`
2. Analyze ALL patterns
3. Create ONE comprehensive solution
4. Test with --dry-run

### 5. Path Navigation  
**BEFORE**: Using `cd` with relative paths  
**STOP**: You'll lose track of location!  
**DO**: Always use absolute paths or verify with `pwd` first

## 🎯 Quick Reference Card

```python
# WRONG                          # RIGHT
ls                              ls -la
python3 script.sh               bash script.sh
cd scripts                      cd /full/path/to/scripts
fix_one_error.py                fix_all_errors.py --dry-run
Read file1; Read file2          Read [file1, file2]  # Batch!
```

## 🔔 Intervention Triggers

Add these to your workflow:

1. **See "No such file"?** → You forgot hidden files → Use `ls -la`
2. **See "SyntaxError"?** → Wrong interpreter → Check with `file`
3. **Multiple similar errors?** → Stop fixing individually → Batch!
4. **Lost in directories?** → Missing pwd check → Always verify location
5. **Can't find .venv?** → Hidden directory → Use find with full path

## 📋 Pre-Flight Checklist

Before ANY task:
```bash
# The "where am I and what do I have" check
pwd && ls -la && which python3

# The "find the venv" check  
find . -name 'activate' -type f 2>/dev/null

# The "what kind of script is this" check
file <script> && head -1 <script>
```
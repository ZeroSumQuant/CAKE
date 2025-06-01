# Cognitive Complexity Explained

Cognitive Complexity measures how hard code is to understand by counting the mental effort needed to follow the logic.

## Key Differences from Cyclomatic Complexity

**Cyclomatic Complexity** counts all decision points equally:
- Every `if`, `for`, `while` = +1
- Doesn't care about nesting or readability

**Cognitive Complexity** considers human understanding:
- Nested conditions are harder (+1 for each level)
- Early returns are easier to follow
- Some patterns are inherently more complex

## Examples

### Example 1: Simple Conditions (Low Cognitive Complexity)
```python
def get_status(user):
    # Cognitive Complexity: 2
    # Easy to understand - linear flow
    
    if not user.is_active:
        return "inactive"
    
    if user.is_admin:
        return "admin"
    
    return "regular"
```

### Example 2: Nested Conditions (High Cognitive Complexity)
```python
def get_status_complex(user):
    # Cognitive Complexity: 6 (much harder!)
    # Each nesting level adds mental burden
    
    if user.is_active:
        if user.is_admin:
            if user.has_2fa:
                return "secure_admin"
            else:
                return "admin"
        else:
            if user.is_premium:
                return "premium"
            else:
                return "regular"
    else:
        return "inactive"
```

### Example 3: Mixed Conditions (Increasing Complexity)
```python
def process_order(order, user, inventory):
    # Cognitive Complexity: 9
    # Multiple concerns mixed together
    
    if order.items:
        for item in order.items:
            if item.quantity > 0:
                if inventory.has_stock(item):
                    if user.can_afford(item.price * item.quantity):
                        try:
                            inventory.reserve(item)
                        except OutOfStock:
                            if item.allow_backorder:
                                order.add_backorder(item)
                            else:
                                return False
                    else:
                        return False
                else:
                    return False
    return True
```

### Example 4: Refactored for Lower Cognitive Complexity
```python
def process_order_simple(order, user, inventory):
    # Cognitive Complexity: 4 (much better!)
    # Early returns and extracted methods
    
    if not order.items:
        return True
    
    for item in order.items:
        if not _can_process_item(item, user, inventory):
            return False
    
    return True

def _can_process_item(item, user, inventory):
    # Cognitive Complexity: 3
    # Single responsibility
    
    if item.quantity <= 0:
        return True
        
    if not inventory.has_stock(item):
        return False
        
    if not user.can_afford(item.price * item.quantity):
        return False
    
    return _try_reserve_item(item, inventory)
```

## What Increases Cognitive Complexity?

1. **Nesting** - Each level makes code harder to follow
2. **Mixed concerns** - Multiple responsibilities in one function
3. **Long chains of if/elif/else**
4. **Breaks in linear flow** (goto, complex continues/breaks)
5. **Recursion** - Harder to trace mentally

## What Reduces Cognitive Complexity?

1. **Early returns** - Fail fast pattern
2. **Guard clauses** - Handle edge cases first
3. **Extract methods** - Single responsibility
4. **Flat is better than nested** - Python Zen
5. **Clear naming** - Self-documenting code

## CAKE Project Guidelines

For CAKE, we limit cognitive complexity to 10 because:
- The Operator component needs to be **deterministic and clear**
- Error handling paths must be **obvious**
- Intervention logic should be **traceable**
- Other developers need to **understand quickly**

## Real Impact Example

```python
# BAD: High Cognitive Complexity (score: 15)
def intervene(error, context, history):
    if error:
        if error.severity > 5:
            if context.is_production:
                if not history.has_recent_intervention(error.type):
                    if context.user.is_experienced:
                        # ... more nesting
                        
# GOOD: Low Cognitive Complexity (score: 5)
def intervene(error, context, history):
    if not should_intervene(error, context, history):
        return None
        
    intervention = create_intervention(error)
    
    if requires_immediate_action(error, context):
        return execute_immediate(intervention)
    
    return schedule_intervention(intervention)
```

## Tools to Measure

- **flake8-cognitive-complexity** - What we use
- **radon** - `radon cc -s file.py`
- **SonarQube** - Enterprise tool
- **CodeClimate** - CI/CD integration

The goal: Write code that's easy for humans to understand, not just computers!
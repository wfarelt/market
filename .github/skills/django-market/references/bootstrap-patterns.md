# Bootstrap 5 — Component Patterns for Market

## Form Layout
```html
<form method="post" class="needs-validation" novalidate>
  {% csrf_token %}
  {% for field in form %}
    <div class="mb-3">
      <label for="{{ field.id_for_label }}" class="form-label">{{ field.label }}</label>
      {{ field }}  {# widget attrs must include class="form-control" #}
      {% if field.errors %}
        <div class="invalid-feedback d-block">{{ field.errors|join:", " }}</div>
      {% endif %}
    </div>
  {% endfor %}
  <button type="submit" class="btn btn-primary">Save</button>
  <a href="{% url '<app>:list' %}" class="btn btn-secondary">Cancel</a>
</form>
```

## Table (list view)
```html
<div class="table-responsive">
  <table class="table table-striped table-hover align-middle">
    <thead class="table-dark">
      <tr>
        <th>Column</th>
      </tr>
    </thead>
    <tbody>
      {% for obj in object_list %}
      <tr>
        <td>{{ obj }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="99" class="text-center text-muted">No records.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
```

## Alert Messages
```html
{% for message in messages %}
<div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
  {{ message }}
  <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
</div>
{% endfor %}
```

## Widget attribute convention
Add Bootstrap classes via `forms.py`:
```python
class ProductForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
```

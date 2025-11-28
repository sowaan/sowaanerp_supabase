### Sowaanerp Supabase

SowaanERP Supabase

This app syncs call and contact data from Supabase to ERPNext Lead records.

## Requirements

1. Add `host_name` to your `site_config.json`:
   
   ```json
   {
     "host_name": "your-erp-site.com"
   }

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app sowaanerp_supabase
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/sowaanerp_supabase
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit

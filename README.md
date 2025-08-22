# nacos-configuration

## Variables
Assign `CI Environment Variables` or you can edit `.env` file to change the configuration of Nacos server or

```ini
# Nacos Configuration
NACOS_SERVER_ADDR=<nacos-server-ip>:8848
NACOS_USERNAME=<username>
NACOS_PASSWORD=<password>

# true if Nacos required password authentication
NACOS_AUTH_ENABLED=true

# Delete configuration files that are not in the export folder if NACOS_DELETE_EXPORT_ONLY is true
NACOS_DELETE_EXPORT_ONLY=false

# Discord Configuration
DISCORD_WEBHOOK_URL=<webhook-url>
```

Put your updated configuration files into the `import` directory.
Make sure the directory structure matches the Nacos configuration structure : <namespace>/<group>/<file>.

```bash
├── import
│   ├── namespace_A
│   │   └── group_1
│   │       └── setting1.yml
│   └── namespace_B
│       └── group_2
│           ├── setting1.properties
│           └── setting2.yml

```

Run the following command to start the deployment process

```sh
./start.sh
```

There will be backup files exported under `export/<namespace>/<group>/<file>`.

```bash

├── export
│   ├── stage
│   ├── dev
│   └── prod
├── import
```

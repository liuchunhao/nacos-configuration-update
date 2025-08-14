# nacos-configuration

## Getting started

Edit `.env` file to change the configuration of Nacos server.

```ini
NACOS_SERVER_ADDR=ec2-15-220-83-112.ap-northeast-1.compute.amazonaws.com:8848
NACOS_USERNAME=nacos
NACOS_PASSWORD=nacos
NACOS_AUTH_ENABLED=true
NACOS_DELETE_EXPORT_ONLY=false
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

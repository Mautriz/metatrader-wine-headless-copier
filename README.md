## How to start

- Copy .env.sample into .env and fill with whatever account credentials you want (for now it only works on FundedElite-Server)
- docker compose up (visit http://localhost:8000/docs)
- whatever position you open/modify/close on the first account will be copied/hedged according to configuration on the other ones

## Important notes

- meta.zip contains a portable installation of metatrader5 working on amd64 architectures, thats why it is just copied and ran with /portable
- volumes/servers.dat is copied in the metatrader5 installation files so that a list of servers is already available, which is the only required thing to connect to an account in headless mode, as of now that only contains fundedelite-server and majesty-fx, so only accounts on those 2 platforms will work, to make other platforms work, we only need to modify servers.data
- volumes/common.ini is to enable algo trading by default and reducing cpu/memory usage

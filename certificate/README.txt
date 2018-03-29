# Copy in this folder your certificate as 'socialcar.crt' and your key as 'socialcar.key'
# NOTE: certificate must be passwordless
cp /etc/ssl/certs/mycertificate.crt   socialcar.crt
cp /etc/ssl/private/mycertificate.key socialcar.key

# ...or create links to them with names 'socialcar.crt' and 'socialcar.key'
# NOTE: certificate must be passwordless
ln -s /etc/ssl/certs/mycertificate.crt   socialcar.crt
ln -s /etc/ssl/private/mycertificate.key socialcar.key

# ...or generate a self-signed certificate without password:
openssl req -x509 -nodes -newkey rsa:4096 -keyout socialcar.key -out socialcar.crt -days 365

# Odoo 19 Namco - Project Layer
#
# Base image provides: Debian bookworm, Python 3.12, Odoo 19 source,
# enterprise modules, system deps, wkhtmltopdf, entrypoint.sh
#
# This layer adds: project-specific odoo.conf, custom Namco addons
#
# Build:
#   docker build -t ghcr.io/baoha-erptek/odoo19-namco:latest .
#   docker build --build-arg BASE_TAG=20260401 -t ghcr.io/baoha-erptek/odoo19-namco:latest .

ARG BASE_TAG=latest
FROM ghcr.io/baoha-erptek/odoo19-base:${BASE_TAG}

USER root

# Copy project-specific Odoo configuration
COPY ./odoo.conf /etc/odoo/
RUN chown odoo /etc/odoo/odoo.conf

# Copy custom Namco addons into image
COPY --chown=odoo:odoo custom_addons/ /opt/odoo/custom_addons/

USER odoo

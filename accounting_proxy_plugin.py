from wstore.asset_manager.resource_plugins.plugin import Plugin
from wstore.asset_manager.resource_plugins.plugin_error import PluginError

from urlparse import urlparse

import requests
import json

class AccountingProxyPlugin(Plugin):

    def record_type(self, unit):
        return {
            'call': 'callusage',
            'megabyte': 'datausage' 
        }[unit]

    def on_post_product_spec_validation(self, provider, asset):
        # Check the url
        url = 'http://' + urlparse(asset.get_url()).netloc + '/api/resources'
        payload = {'url': asset.get_url()}

        resp = requests.post(url, json=payload)

        if resp.status_code != 200:
            raise PluginError('Invalid asset url')


    def on_pre_product_offering_validation(self, asset, product_offering):
        # Check supported accounting units
        url = 'http://' + urlparse(asset.get_url()).netloc + '/api/units'

        resp = requests.get(url)

        if resp.status_code != 200:
            raise PlugginError('Error checking the supported accounting units')
        else:
            units = json.loads(resp.text)['units']

            for price_model in product_offering['productOfferingPrice']:

                if price_model['priceType'] == 'usage' and price_model['unitOfMeasure'] not in units:
                    raise PluginError('Unsupported accounting unit ' + price_model['unit'] + '. Supported units are: ' + units)


    def on_product_acquisition(self, asset, contract, order):
        # Send new buy notification to the accounting proxy
        url = 'http://' + urlparse(asset.get_url()).netloc + '/api/users'

        for price_model in contract.pricing_model:
            if 'unit' in price_model:
                unit = price_model['unit']

        payload = { 
            'productId': asset.product_id,
            'orderId': order.order_id,
            'customer': order.customer,
            'productSpecification': {
                'url': order.offering.href,
                'unit': unit,
                'recordType': self.record_type(unit)
            }
        }

        resp = requests.post(url, json=payload)

        if resp.status_code != 201:
            raise PluginError('Error notifying the product acquisition to the accounting proxy')
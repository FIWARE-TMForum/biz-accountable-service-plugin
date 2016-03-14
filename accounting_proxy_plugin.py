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
        url = urlparse(asset.get_url()).scheme + '://' + urlparse(asset.get_url()).netloc + '/accounting_proxy/urls'
        payload = {'url': asset.get_url()}

        resp = requests.post(url, json=payload)

        if resp.status_code != 200:
            raise PluginError('Invalid asset url')


    def on_post_product_offering_validation(self, asset, product_offering):
        # Check supported accounting units
        url = urlparse(asset.get_url()).scheme + '://' + urlparse(asset.get_url()).netloc + '/accounting_proxy/units'

        resp = requests.get(url)

        if resp.status_code != 200:
            raise PluginError('Error checking the supported accounting units')
        else:
            units = resp.json()['units']
            found = False

            for price_model in product_offering['productOfferingPrice']:

                if price_model['priceType'] == 'usage' and price_model['unitOfMeasure'] not in units:
                    raise PluginError('Unsupported accounting unit ' + price_model['unit'] + '. Supported units are: ' + units)
                if price_model['priceType'] == 'usage' and price_model['unitOfMeasure'] in units:
                    found = True

            if not fount:
                raise PluginError('No "usage" price type in the product_offering')

    def on_product_acquisition(self, asset, contract, order):
        # Send new buy notification to the accounting proxy
        url = urlparse(asset.get_url()).scheme + '://' + urlparse(asset.get_url()).netloc + '/accounting_proxy/buys'

        if 'pay per use' in contract.pricing_model:

            count = 0
            for price_model in contract.pricing_model['pay per use']:
                if 'unit' in price_model:
                    unit = price_model['unit']
                    count += 1

            if count != 1:
                raise PluginError('Wrong number of pricing components. Only supported one pricing component')
            else:

                payload = { 
                    'productId': asset.product_id,
                    'orderId': order.order_id,
                    'customer': order.customer,
                    'productSpecification': {
                        'url': order.asset.get_url(),
                        'unit': unit,
                        'recordType': self.record_type(unit)
                    }
                }

                resp = requests.post(url, json=payload)

                if resp.status_code != 201:
                    raise PluginError('Error notifying the product acquisition to the accounting proxy')
        else 
            raise PluginError('Contract must have a "pay per use" in the pricing_model')
import logging
import pdb
import pytz
import random
import requests
import requests_futures.sessions
import unittest

from datetime import datetime, timezone, time, timedelta
from db_service import DbService
from traffic_violations_aggregator import TrafficViolationsAggregator
from unittest.mock import call, MagicMock, patch


def create_error(arg):
    raise ValueError('generic error')


class TestTrafficViolationsAggregator(unittest.TestCase):

    def setUp(self):
        logger          = logging.getLogger('hows_my_driving')
        db_service      = DbService(logger)
        self.aggregator = TrafficViolationsAggregator(db_service, logger, '')



    def test_detect_borough(self):
        bronx_comp = {
          'results': [
            {
              'address_components': [
                {
                  'long_name': 'Bronx',
                  'short_name': 'Bronx',
                  'types': [
                    'political',
                    'sublocality',
                    'sublocality_level_1'
                  ]
                }
              ]
            }
          ]
        }

        empty_comp = {
          'results': [
            {
              'address_components': [
                {}
              ]
            }
          ]
        }

        req_mock = MagicMock(name='json')
        req_mock.json.return_value = bronx_comp

        get_mock = MagicMock(name='get')
        get_mock.return_value = req_mock

        requests.get = get_mock

        self.assertEqual(self.aggregator.detect_borough('Da Bronx'), ['Bronx'])


        req_mock.json.return_value = empty_comp

        self.assertEqual(self.aggregator.detect_borough('no match'), [])



    def test_detect_campaign_hashtags(self):
        cursor_mock = MagicMock(name='cursor')
        cursor_mock.cursor = [[6, '#TestCampaign']]

        execute_mock = MagicMock(name='execute')
        execute_mock.execute.return_value = cursor_mock

        connect_mock = MagicMock(name='connect')
        connect_mock.return_value = execute_mock

        self.aggregator.db_service = connect_mock
        self.aggregator.db_service.__enter__ = connect_mock

        self.assertEqual(self.aggregator.detect_campaign_hashtags(['#TestCampaign'])[0][1], '#TestCampaign')
        self.assertEqual(self.aggregator.detect_campaign_hashtags(['#TestCampaign,'])[0][1], '#TestCampaign')


    def test_detect_state(self):
        str     = '99|AB|AK|AL|AR|AZ|BC|CA|CO|CT|DC|DE|DP|FL|FM|FO|GA|GU|GV|HI|IA|ID|IL|IN|KS|KY|LA|MA|MB|MD|ME|MI|MN|MO|MP|MS|MT|MX|NB|NC|ND|NE|NF|NH|NJ|NM|NS|NT|NV|NY|OH|OK|ON|OR|PA|PE|PR|PW|QC|RI|SC|SD|SK|TN|TX|UT|VA|VI|VT|WA|WI|WV|WY|YT'
        regions = str.split('|')

        for region in regions:
            self.assertEqual(self.aggregator.detect_state(region), True)
            self.assertEqual(self.aggregator.detect_state(region + 'XX'), False)


    def test_find_max_camera_streak(self):
        list_of_camera_times1 = [
          datetime(2015, 9, 18, 0, 0),
          datetime(2015, 10, 16, 0, 0),
          datetime(2015, 11, 2, 0, 0),
          datetime(2015, 11, 5, 0, 0),
          datetime(2015, 11, 12, 0, 0),
          datetime(2016, 2, 2, 0, 0),
          datetime(2016, 2, 25, 0, 0),
          datetime(2016, 5, 31, 0, 0),
          datetime(2016, 9, 8, 0, 0),
          datetime(2016, 10, 17, 0, 0),
          datetime(2016, 10, 24, 0, 0),
          datetime(2016, 10, 26, 0, 0),
          datetime(2016, 11, 21, 0, 0),
          datetime(2016, 12, 18, 0, 0),
          datetime(2016, 12, 22, 0, 0),
          datetime(2017, 1, 5, 0, 0),
          datetime(2017, 2, 13, 0, 0),
          datetime(2017, 5, 10, 0, 0),
          datetime(2017, 5, 24, 0, 0),
          datetime(2017, 6, 27, 0, 0),
          datetime(2017, 6, 27, 0, 0),
          datetime(2017, 9, 14, 0, 0),
          datetime(2017, 11, 6, 0, 0),
          datetime(2018, 1, 28, 0, 0)
        ]

        result1 = {
          'min_streak_date': 'September 8, 2016',
          'max_streak': 13,
          'max_streak_date': 'June 27, 2017'
        }

        self.assertEqual(self.aggregator.find_max_camera_violations_streak(list_of_camera_times1), result1)


    def test_find_potential_vehicles(self):
      string_parts       = ['@HowsMyDrivingNY', 'I', 'found', 'some', 'more', 'ny:123abcd', 'ca:6vmd948', 'xx:7kvj935', 'state:fl', 'plate:d4kdm4']

      potential_vehicles = [
        {'original_string':'ny:123abcd', 'state': 'ny', 'plate': '123abcd', 'valid_plate': True},
        {'original_string':'ca:6vmd948', 'state': 'ca', 'plate': '6vmd948', 'valid_plate': True},
        {'original_string':'xx:7kvj935', 'valid_plate': False}
      ]

      self.assertEqual(self.aggregator.find_potential_vehicles(string_parts), potential_vehicles)


    def test_find_potential_vehicles_using_legacy_logic(self):
        string_parts1       = ['@HowsMyDrivingNY', 'I', 'found', 'some', 'more', 'ny:123abcd', 'ca:6vmd948', 'xx:7kvj935', 'state:fl', 'plate:d4kdm4']
        string_parts2       = ['@HowsMyDrivingNY', 'I', 'love', 'you', 'very', 'much!']
        string_parts3       = ['@HowsMyDrivingNY', 'I', 'found', 'some', 'more', 'state:fl', 'plate:d4kdm4', 'types:pas,com']
        potential_vehicles1 = [{'state': 'fl', 'plate': 'd4kdm4', 'valid_plate': True}]
        potential_vehicles3 = [{'state': 'fl', 'plate': 'd4kdm4', 'valid_plate': True, 'types': 'pas,com'}]

        self.assertEqual(self.aggregator.find_potential_vehicles_using_legacy_logic(string_parts1), potential_vehicles1)
        self.assertEqual(self.aggregator.find_potential_vehicles_using_legacy_logic(string_parts2), [])
        self.assertEqual(self.aggregator.find_potential_vehicles_using_legacy_logic(string_parts3), potential_vehicles3)


    def test_form_campaign_lookup_response_parts(self):
        campaign_data1 = {'included_campaigns': [{'campaign_hashtag': '#SaferSkillman', 'campaign_tickets': 71, 'campaign_vehicles': 6}]}
        campaign_data2 = {'included_campaigns': [{'campaign_hashtag': '#BetterPresident', 'campaign_tickets': 1, 'campaign_vehicles': 1}]}
        campaign_data3 = {'included_campaigns': [{'campaign_hashtag': '#BusTurnaround', 'campaign_tickets': 0, 'campaign_vehicles': 1}]}

        self.assertEqual(self.aggregator.form_campaign_lookup_response_parts(campaign_data1, '@bdhowald'), ['@bdhowald 6 vehicles with a total of 71 tickets have been tagged with #SaferSkillman.\n\n'])
        self.assertEqual(self.aggregator.form_campaign_lookup_response_parts(campaign_data2, '@BarackObama'), ['@BarackObama 1 vehicle with 1 ticket has been tagged with #BetterPresident.\n\n'])
        self.assertEqual(self.aggregator.form_campaign_lookup_response_parts(campaign_data3, '@FixQueensBlvd'), ['@FixQueensBlvd 1 vehicle with 0 tickets has been tagged with #BusTurnaround.\n\n'])


    def test_form_plate_lookup_response_parts(self):
        previous_time = datetime.now() - timedelta(minutes=10)
        utc           = pytz.timezone('UTC')
        eastern       = pytz.timezone('US/Eastern')

        adjusted_time = utc.localize(previous_time).astimezone(eastern)


        plate_lookup1 = {
          'plate': 'HME6483',
          'plate_types': 'pas',
          'state': 'NY',
          'violations': [
            {'title': 'No Standing - Day/Time Limits', 'count': 14},
            {'title': 'No Parking - Street Cleaning', 'count': 3},
            {'title': 'Failure To Display Meter Receipt', 'count': 1},
            {'title': 'No Violation Description Available', 'count': 1},
            {'title': 'Bus Lane Violation', 'count': 1},
            {'title': 'Failure To Stop At Red Light', 'count': 1},
            {'title': 'No Standing - Commercial Meter Zone', 'count': 1},
            {'title': 'Expired Meter', 'count': 1},
            {'title': 'Double Parking', 'count': 1},
            {'title': 'No Angle Parking', 'count': 1}
          ],
          'years': [
            {'title': '2016', 'count': 2},
            {'title': '2017', 'count': 8},
            {'title': '2018', 'count': 13}
          ],
          'previous_result': {
            'num_tickets': 23,
            'created_at': previous_time
          },
          'frequency': 8,
          'boroughs': [
            {'count': 1, 'title': 'Bronx'},
            {'count': 7, 'title': 'Brooklyn'},
            {'count': 2, 'title': 'Queens'},
            {'count': 13, 'title': 'Staten Island'}
          ],
          'fines': [
            ('fined', 180,),
            ('reduced', 50,),
            ('paid', 100,),
            ('outstanding', 30,),
          ],
          'camera_streak_data': {
            'min_streak_date': 'September 18, 2015',
            'max_streak': 4,
            'max_streak_date': 'November 5, 2015'
          }
        }

        response_parts1 = [
          '@bdhowald #NY_HME6483 (types: pas) has been queried 8 times.\n'
          '\n'
          'Since the last time the vehicle was queried (' + adjusted_time.strftime('%B %e, %Y') + ' at ' + adjusted_time.strftime('%I:%M%p') + '), '
          '#NY_HME6483 has received 2 new tickets.\n'
          '\n'
          'Total parking and camera violation tickets: 25\n'
          '\n'
          '14 | No Standing - Day/Time Limits\n',
          "@bdhowald Parking and camera violation tickets for #NY_HME6483, cont'd:\n"
          '\n'
          '3   | No Parking - Street Cleaning\n'
          '1   | Failure To Display Meter Receipt\n'
          '1   | No Violation Description Available\n'
          '1   | Bus Lane Violation\n'
          '1   | Failure To Stop At Red Light\n',
          "@bdhowald Parking and camera violation tickets for #NY_HME6483, cont'd:\n"
          '\n'
          '1   | No Standing - Commercial Meter Zone\n'
          '1   | Expired Meter\n'
          '1   | Double Parking\n'
          '1   | No Angle Parking\n',
          '@bdhowald Violations by year for #NY_HME6483:\n'
          '\n'
          '2   | 2016\n'
          '8   | 2017\n'
          '13 | 2018\n',
          '@bdhowald Violations by borough for #NY_HME6483:\n'
          '\n'
          '1   | Bronx\n'
          '7   | Brooklyn\n'
          '2   | Queens\n'
          '13 | Staten Island\n',
          '@bdhowald Known fines for #NY_HME6483:\n'
          '\n'
          '$180.00 | Fined\n'
          '$50.00   | Reduced\n'
          '$100.00 | Paid\n'
          '$30.00   | Outstanding\n'
        ]

        self.assertEqual(self.aggregator.form_plate_lookup_response_parts(plate_lookup1, '@bdhowald'), response_parts1)


        plate_lookup2 = {
          'plate': 'HME6483',
          'plate_types': None,
          'state': 'NY',
          'violations': [
            {'title': 'No Standing - Day/Time Limits', 'count': 14},
            {'title': 'No Parking - Street Cleaning', 'count': 3},
            {'title': 'Failure To Display Meter Receipt', 'count': 1},
            {'title': 'No Violation Description Available', 'count': 1},
            {'title': 'Bus Lane Violation', 'count': 1},
            {'title': 'Failure To Stop At Red Light', 'count': 1},
            {'title': 'No Standing - Commercial Meter Zone', 'count': 1},
            {'title': 'Expired Meter', 'count': 1},
            {'title': 'Double Parking', 'count': 1},
            {'title': 'No Angle Parking', 'count': 1}
          ],
          'years': [
            {'title': '2016', 'count': 2},
            {'title': '2017', 'count': 8},
            {'title': '2018', 'count': 13}
          ],
          'previous_result': {
            'num_tickets': 23,
            'created_at': previous_time
          },
          'frequency': 8,
          'boroughs': [
            {'count': 1, 'title': 'Bronx'},
            {'count': 7, 'title': 'Brooklyn'},
            {'count': 2, 'title': 'Queens'},
            {'count': 13, 'title': 'Staten Island'}
          ],
          'fines': [
            ('fined', 0,),
            ('reduced', 0,),
            ('paid', 0,),
            ('outstanding', 0,),
          ],
          'camera_streak_data': {
            'min_streak_date': 'September 18, 2015',
            'max_streak': 5,
            'max_streak_date': 'November 5, 2015'
          }
        }

        response_parts2 = [
          '@bdhowald #NY_HME6483 has been queried 8 times.\n'
          '\n'
          'Since the last time the vehicle was queried (' + adjusted_time.strftime('%B %e, %Y') + ' at ' + adjusted_time.strftime('%I:%M%p') + '), '
          '#NY_HME6483 has received 2 new tickets.\n'
          '\n'
          'Total parking and camera violation tickets: 25\n'
          '\n'
          '14 | No Standing - Day/Time Limits\n',
          "@bdhowald Parking and camera violation tickets for #NY_HME6483, cont'd:\n"
          '\n'
          '3   | No Parking - Street Cleaning\n'
          '1   | Failure To Display Meter Receipt\n'
          '1   | No Violation Description Available\n'
          '1   | Bus Lane Violation\n'
          '1   | Failure To Stop At Red Light\n',
          "@bdhowald Parking and camera violation tickets for #NY_HME6483, cont'd:\n"
          '\n'
          '1   | No Standing - Commercial Meter Zone\n'
          '1   | Expired Meter\n'
          '1   | Double Parking\n'
          '1   | No Angle Parking\n',
          '@bdhowald Violations by year for #NY_HME6483:\n'
          '\n'
          '2   | 2016\n'
          '8   | 2017\n'
          '13 | 2018\n',
          '@bdhowald Violations by borough for #NY_HME6483:\n'
          '\n'
          '1   | Bronx\n'
          '7   | Brooklyn\n'
          '2   | Queens\n'
          '13 | Staten Island\n',
          "@bdhowald Under @bradlander's proposed legislation, this vehicle could have been booted or impounded due to its 5 camera violations (>= 5/year) from September 18, 2015 to November 5, 2015.\n",
        ]

        self.assertEqual(self.aggregator.form_plate_lookup_response_parts(plate_lookup2, '@bdhowald'), response_parts2)


    def test_form_summary_string(self):

      username     = '@bdhowald'

      fined        = random.randint(10, 20000)
      reduced      = random.randint(0, fined)
      paid         = random.randint(0, fined - reduced)

      num_tickets  = random.randint(10, 20000)

      num_vehicles = random.randint(2,5)

      summary = {
        'fines': {
          'fined'      : fined,
          'outstanding': fined - reduced - paid,
          'paid'       : paid,
          'reduced'    : reduced
        },
        'tickets'  : num_tickets,
        'vehicles' : num_vehicles
      }

      self.assertEqual(self.aggregator.form_summary_string(summary, username), ["@bdhowald The {} vehicles you queried have collectively received {} tickets with at least {} in fines, of which {} has been paid.\n\n".format(num_vehicles, num_tickets, '${:,.2f}'.format(fined - reduced), '${:,.2f}'.format(paid))])


    def test_handle_response_part_formation(self):

        plate      = 'HME6483'
        state      = 'NY'
        username   = '@NYC_DOT'

        collection = [
          {'title': '2017', 'count': 1},
          {'title': '2018', 'count': 1}
        ]

        keys       = {
          'count'                       : 'count',
          'continued_format_string'     : "Violations by year for #{}_{}:, cont'd\n\n",
          'continued_format_string_args': [state, plate],
          'cur_string'                  : '',
          'description'                 : 'title',
          'default_description'         : 'No Year Available',
          'prefix_format_string'        : 'Violations by year for #{}_{}:\n\n',
          'prefix_format_string_args'   : [state, plate],
          'result_format_string'        : '{}| {}\n',
          'username'                    : username
        }

        result     = [(username + ' ' + keys['prefix_format_string']).format(state, plate) + '1 | 2017\n1 | 2018\n']

        self.assertEqual(self.aggregator.handle_response_part_formation(collection, keys), result)


    def test_initiate_reply(self):
        rand_int = random.randint(10000000000000000000, 20000000000000000000)
        now      = datetime.now()
        utc      = pytz.timezone('UTC')
        now_str  = utc.localize(now).astimezone(timezone.utc).strftime('%a %b %d %H:%M:%S %z %Y')

        direct_message_mock = MagicMock(spec=[u'a'])
        direct_message_mock.direct_message = {
          'created_at': now,
          'id': rand_int,
          'recipient': {
            'screen_name': 'HowsMyDrivingNY'
          },
          'sender': {
            'screen_name': 'bdhowald',
            'id': 30139847
          },
          'text': '@HowsMyDrivingNY ny:123abcd ca:cad4534 ny:456efgh'
        }

        direct_message_args_for_response = {
          'created_at': now,
          'id': rand_int,
          'legacy_string_parts': [
            '@howsmydrivingny',
            'ny:123abcd',
            'ca:cad4534',
            'ny:456efgh'
          ],
          'string_parts': [
            '@howsmydrivingny',
            'ny:123abcd',
            'ca:cad4534',
            'ny:456efgh'
          ],
          'user_id': 30139847,
          'username': 'bdhowald',
          'type': 'direct_message'
        }


        entities_mock = MagicMock(spec=[u'b'])
        entities_mock.created_at      = now
        entities_mock.entities        = {
          'user_mentions': [
            {
              'screen_name': 'HowsMyDrivingNY'
            },
            {
              'screen_name': 'BarackObama'
            }
          ]
        }
        entities_mock.id             = rand_int
        entities_mock.text           = '@HowsMyDrivingNY ny:123abcd:abc ca:cad4534:zyx ny:456efgh bex:az:1234567'

        user_mock             = MagicMock('screen_name')
        user_mock.screen_name = 'bdhowald'
        user_mock.id          = 30139847

        entities_mock.user           = user_mock

        entities_args_for_response   = {
          'created_at': now_str,
          'id': rand_int,
          'legacy_string_parts': [
            '@howsmydrivingny',
            'ny:123abcd:abc',
            'ca:cad4534:zyx',
            'ny:456efgh',
            'bex:az:1234567'
          ],
          'mentioned_users': [
            'howsmydrivingny',
            'barackobama'
          ],
          'string_parts': [
            '@howsmydrivingny',
            'ny:123abcd:abc',
            'ca:cad4534:zyx',
            'ny:456efgh',
            'bex:az:1234567'
          ],
          'user_id': 30139847,
          'username': 'bdhowald',
          'type': 'status'
        }


        extended_tweet_mock = MagicMock(spec=[u'c'])
        extended_tweet_mock.created_at      = now
        extended_tweet_mock.extended_tweet = {
          'entities': {
            'user_mentions': [
              {
                'screen_name': 'HowsMyDrivingNY'
              },
              {
                'screen_name': 'BarackObama'
              }
            ]
          },
          'full_text': '@HowsMyDrivingNY ny:ny ca:1234567'
        }
        extended_tweet_mock.id             = rand_int

        # user_mock             = MagicMock('screen_name')
        # user_mock.screen_name = 'bdhowald'

        extended_tweet_mock.user           = user_mock

        extended_tweet_args_for_response   = {
          'created_at': now_str,
          'id': rand_int,
          'legacy_string_parts': [
            '@howsmydrivingny',
            'ny:ny',
            'ca:1234567'
          ],
          'mentioned_users': [
            'howsmydrivingny',
            'barackobama'
          ],
          'string_parts': [
            '@howsmydrivingny',
            'ny:ny',
            'ca:1234567'
          ],
          'user_id': 30139847,
          'username': 'bdhowald',
          'type': 'status'
        }



        process_response_message_mock = MagicMock(name='process_response_message')

        self.aggregator.process_response_message = process_response_message_mock


        self.aggregator.initiate_reply(direct_message_mock, 'direct_message')

        process_response_message_mock.assert_called_with(direct_message_args_for_response)


        self.aggregator.initiate_reply(entities_mock, 'status')

        process_response_message_mock.assert_called_with(entities_args_for_response)


        self.aggregator.initiate_reply(extended_tweet_mock, 'status')

        process_response_message_mock.assert_called_with(extended_tweet_args_for_response)


    def test_infer_plate_and_state_data(self):
        plate_tuples = [['ny', '123abcd'], ['ca', ''], ['xx', 'pxk3819'], ['99', '1234']]

        result = [
          {'original_string':'ny:123abcd', 'state': 'ny', 'plate': '123abcd', 'valid_plate': True},
          {'original_string': 'ca:', 'valid_plate': False},
          {'original_string': 'xx:pxk3819', 'valid_plate': False},
          {'original_string':'99:1234', 'state': '99', 'plate': '1234', 'valid_plate': True}
        ]

        self.assertEqual(self.aggregator.infer_plate_and_state_data(plate_tuples),result)


        plate_tuples = []

        self.assertEqual(self.aggregator.infer_plate_and_state_data(plate_tuples),[])


        plate_tuples = [['ny', 'ny']]

        self.assertEqual(self.aggregator.infer_plate_and_state_data(plate_tuples),[{'original_string':'ny:ny', 'state': 'ny', 'plate': 'ny', 'valid_plate': True}])


    def test_perform_campaign_lookup(self):
        included_campaigns = [
          (1, '#SaferSkillman')
        ]

        result = {
          'included_campaigns': [
            {
              'campaign_hashtag': '#SaferSkillman',
              'campaign_tickets': 7167,
              'campaign_vehicles': 152
            }
          ]
        }

        cursor_mock = MagicMock(name='cursor')
        cursor_mock.fetchone.return_value = (152, 7167)

        execute_mock = MagicMock(name='execute')
        execute_mock.execute.return_value = cursor_mock
        # tweeter.
        connect_mock = MagicMock(name='connect')
        connect_mock.return_value = execute_mock

        self.aggregator.db_service = connect_mock
        self.aggregator.db_service.__enter__ = connect_mock

        self.assertEqual(self.aggregator.perform_campaign_lookup(included_campaigns), result)



    def test_perform_plate_lookup(self):
        rand_int = random.randint(10000000000000000000, 20000000000000000000)
        now      = datetime.now()
        previous = now - timedelta(minutes=10)
        utc      = pytz.timezone('UTC')
        now_str  = utc.localize(now).astimezone(timezone.utc).strftime('%a %b %d %H:%M:%S %z %Y')

        args = {
          'created_at': now_str,
          'message_id': rand_int,
          'message_type': 'direct_message',
          'included_campaigns': [(87, '#BetterPresident')],
          'plate': 'ABCDEFG',
          'plate_types': 'com,pas',
          'state': 'ny',
          'username': 'bdhowald'
        }

        violations = [
          {
            'amount_due': '0',
            'county': 'NY',
            'fine_amount': '100',
            'interest_amount': '0',
            'issue_date': '01/19/2017',
            'issuing_agency': 'TRAFFIC',
            'license_type': 'PAS',
            'payment_amount': '0',
            'penalty_amount': '0',
            'plate': 'HME6483',
            'precinct': '005',
            'reduction_amount': '0',
            'state': 'NY',
            'summons_image': 'http://nycserv.nyc.gov/NYCServWeb/ShowImage?searchID=VDBSVmQwNVVaekZOZWxreFQxRTlQUT09&locationName=_____________________',
            'summons_image_description': 'View Summons',
            'summons_number': '8505853659',
            'violation_status': 'HEARING HELD-NOT GUILTY',
            'violation_time': '08:39P'
          },
          {
            'amount_due': '0',
            'county': 'NY',
            'fine_amount': '50',
            'interest_amount': '0',
            'issue_date': '01/20/2018',
            'issuing_agency': 'TRAFFIC',
            'license_type': 'PAS',
            'payment_amount': '0',
            'penalty_amount': '0',
            'plate': 'HME6483',
            'precinct': '005',
            'reduction_amount': '20',
            'state': 'NY',
            'summons_image': 'http://nycserv.nyc.gov/NYCServWeb/ShowImage?searchID=VDBSVmQwNVVaekZOZWxreFQxRTlQUT09&locationName=_____________________',
            'summons_image_description': 'View Summons',
            'summons_number': '8505853660',
            'violation': 'FAIL TO DSPLY MUNI METER RECPT',
            'violation_description': 'FAIL TO DSPLY MUNI METER RECPT',
            'violation_status': 'HEARING HELD-NOT GUILTY',
            'violation_time': '08:40P'
          }
        ]

        result = {
          'plate': 'ABCDEFG',
          'plate_types': 'com,pas',
          'state': 'NY',
          'violations': [
            {
              'count': 1,
              'title': 'No Violation Description Available'
            },
            {
              'count': 1,
              'title': 'Fail To Dsply Muni Meter Recpt'
            }
          ],
          'years': [
            {'title': '2017', 'count': 1},
            {'title': '2018', 'count': 1}
          ],
          'previous_result': {},
          'frequency': 2,
          'boroughs': [
            {'count': 2, 'title': 'Manhattan'}
          ],
          'fines': [('fined', 150.0), ('reduced', 20.0), ('paid', 0), ('outstanding', 0)],
        }

        violations_mock = MagicMock(name='violations')
        violations_mock.json.return_value = violations
        violations_mock.status_code = 200

        result_mock = MagicMock(name='result')
        result_mock.result.return_value = violations_mock

        get_mock = MagicMock(name='get')
        get_mock.return_value = result_mock

        session_mock = MagicMock(name='session_object')
        session_mock.get = get_mock

        session_object_mock = MagicMock(name='session_object')
        session_object_mock.return_value = session_mock


        requests_futures.sessions.FuturesSession = session_object_mock

        cursor_mock = MagicMock(name='cursor')
        cursor_mock.cursor = [{'num_tickets': 1, 'created_at': previous}]
        cursor_mock.fetchone.return_value = (1,)

        execute_mock = MagicMock(name='execute')
        execute_mock.execute.return_value = cursor_mock
        # tweeter.
        connect_mock = MagicMock(name='connect')
        connect_mock.return_value = execute_mock

        self.aggregator.db_service = connect_mock
        self.aggregator.db_service.__enter__ = connect_mock

        self.assertEqual(self.aggregator.perform_plate_lookup(args), result)


        # Try again with a forced error.

        error_result = {'error': 'server error', 'plate': 'ABCDEFG', 'state': 'NY'}

        violations_mock.status_code = 503

        self.assertEqual(self.aggregator.perform_plate_lookup(args), error_result)


    def test_process_response_message(self):
        now           = datetime.now()
        previous_time = now - timedelta(minutes=10)
        utc           = pytz.timezone('UTC')
        eastern       = pytz.timezone('US/Eastern')
        utc_time      = utc.localize(now).astimezone(timezone.utc)
        # eastern_time  = utc.localize(now).astimezone(eastern)
        previous_utc  = utc.localize(previous_time).astimezone(timezone.utc)



        ######################################
        # Test direct message and new format #
        ######################################

        username1   = 'bdhowald'
        message_id  = random.randint(1000000000000000000, 2000000000000000000)
        response_args1 = {
          'created_at': utc_time.strftime('%a %b %d %H:%M:%S %z %Y'),
          'id': message_id,
          'legacy_string_parts': ['@howsmydrivingny',
                                  'ny:hme6483'],
          'string_parts': ['@howsmydrivingny',
                           'ny:hme6483'],
          'type': 'direct_message',
          'username': username1,
          'user_id': 30139847
        }
        plate_lookup1 = {
          'fines': [('fined', 200.0), ('outstanding', 125.0), ('paid', 75.0)],
          'frequency': 1,
          'plate': 'HME6483',
          'plate_types': None,
          'previous_result': {'created_at': previous_time,
                               'num_tickets': 15},
          'state': 'NY',
          'violations': [{'count': 4, 'title': 'No Standing - Day/Time Limits'},
                         {'count': 3, 'title': 'No Parking - Street Cleaning'},
                         {'count': 1, 'title': 'Failure To Display Meter Receipt'},
                         {'count': 1, 'title': 'No Violation Description Available'},
                         {'count': 1, 'title': 'Bus Lane Violation'},
                         {'count': 1, 'title': 'Failure To Stop At Red Light'},
                         {'count': 1, 'title': 'No Standing - Commercial Meter Zone'},
                         {'count': 1, 'title': 'Expired Meter'},
                         {'count': 1, 'title': 'Double Parking'},
                         {'count': 1, 'title': 'No Angle Parking'}
          ],
          'years': [
            {'title': '2017', 'count': 10},
            {'title': '2018', 'count': 15}
          ]
        }

        combined_message = "@bdhowald #NY_HME6483 has been queried 1 time.\n\nTotal parking and camera violation tickets: 15\n\n4 | No Standing - Day/Time Limits\n3 | No Parking - Street Cleaning\n1 | Failure To Display Meter Receipt\n1 | No Violation Description Available\n1 | Bus Lane Violation\n\n@bdhowald Parking and camera violation tickets for #NY_HME6483, cont'd:\n\n1 | Failure To Stop At Red Light\n1 | No Standing - Commercial Meter Zone\n1 | Expired Meter\n1 | Double Parking\n1 | No Angle Parking\n\n@bdhowald Violations by year for #NY_HME6483:\n\n10 | 2017\n15 | 2018\n\n@bdhowald Known fines for #NY_HME6483:\n\n$200.00 | Fined\n$125.00 | Outstanding\n$75.00   | Paid\n"


        response1 = {
          'error_on_lookup'  : False,
          'response_args'    : response_args1,
          'response_parts'   : [
            [
              '@bdhowald #NY_HME6483 has been queried 1 time.\n'
              '\n'
              'Total parking and camera violation tickets: 15\n'
              '\n'
              '4 | No Standing - Day/Time Limits\n'
              '3 | No Parking - Street Cleaning\n'
              '1 | Failure To Display Meter Receipt\n'
              '1 | No Violation Description Available\n'
              '1 | Bus Lane Violation\n',
              '@bdhowald Parking and camera violation tickets for '
              "#NY_HME6483, cont'd:\n"
              '\n'
              '1 | Failure To Stop At Red Light\n'
              '1 | No Standing - Commercial Meter Zone\n'
              '1 | Expired Meter\n'
              '1 | Double Parking\n'
              '1 | No Angle Parking\n',
              '@bdhowald Violations by year for #NY_HME6483:\n'
              '\n'
              '10 | 2017\n'
              '15 | 2018\n',
              '@bdhowald Known fines for #NY_HME6483:\n'
              '\n'
              '$200.00 | Fined\n'
              '$125.00 | Outstanding\n'
              '$75.00   | Paid\n'
            ]
          ],
          'success'          : True,
          'successful_lookup': True
        }

        plate_lookup_mock = MagicMock(name='plate_lookup')
        plate_lookup_mock.return_value = plate_lookup1

        send_direct_message_mock = MagicMock('send_direct_message_mock')

        api_mock = MagicMock(name='api')
        api_mock.send_direct_message_new  = send_direct_message_mock

        self.aggregator.perform_plate_lookup = plate_lookup_mock
        self.aggregator.api = api_mock

        self.assertEqual(self.aggregator.process_response_message(response_args1), response1)




        ##############################
        # Test status and old format #
        ##############################

        username2      = 'BarackObama'
        response_args2 = {
          'created_at': utc_time.strftime('%a %b %d %H:%M:%S %z %Y'),
          'id': message_id,
          'legacy_string_parts': ['@howsmydrivingny',
                                  'plate:glf7467',
                                  'state:pa'],
          'string_parts': ['@howsmydrivingny',
                           'plate:glf7467'
                           'state:pa'],
          'type': 'status',
          'username': username2
        }
        plate_lookup2 = {
          'fines': [('fined', 1000.0), ('outstanding', 225.0), ('paid', 775.0)],
          'frequency': 1,
          'plate': 'GLF7467',
          'plate_types': None,
          'previous_result': {'created_at': previous_time,
                              'num_tickets': 49},
          'state': 'PA',
          'violations': [{'count': 17, 'title': 'No Parking - Street Cleaning'},
                         {'count': 6, 'title': 'Expired Meter'},
                         {'count': 5, 'title': 'No Violation Description Available'},
                         {'count': 3, 'title': 'Fire Hydrant'},
                         {'count': 3, 'title': 'No Parking - Day/Time Limits'},
                         {'count': 3, 'title': 'Failure To Display Meter Receipt'},
                         {'count': 3, 'title': 'School Zone Speed Camera Violation'},
                         {'count': 2, 'title': 'No Parking - Except Authorized Vehicles'},
                         {'count': 2, 'title': 'Bus Lane Violation'},
                         {'count': 1, 'title': 'Failure To Stop At Red Light'},
                         {'count': 1, 'title': 'No Standing - Day/Time Limits'},
                         {'count': 1, 'title': 'No Standing - Except Authorized Vehicle'},
                         {'count': 1, 'title': 'Obstructing Traffic Or Intersection'},
                         {'count': 1, 'title': 'Double Parking'}]
        }

        response_parts2 = [['@BarackObama #PA_GLF7467 has been queried 1 time.\n\nTotal parking and camera violation tickets: 49\n\n17 | No Parking - Street Cleaning\n6   | Expired Meter\n5   | No Violation Description Available\n3   | Fire Hydrant\n3   | No Parking - Day/Time Limits\n', "@BarackObama Parking and camera violation tickets for #PA_GLF7467, cont'd:\n\n3   | Failure To Display Meter Receipt\n3   | School Zone Speed Camera Violation\n2   | No Parking - Except Authorized Vehicles\n2   | Bus Lane Violation\n1   | Failure To Stop At Red Light\n", "@BarackObama Parking and camera violation tickets for #PA_GLF7467, cont'd:\n\n1   | No Standing - Day/Time Limits\n1   | No Standing - Except Authorized Vehicle\n1   | Obstructing Traffic Or Intersection\n1   | Double Parking\n", '@BarackObama Known fines for #PA_GLF7467:\n\n$1,000.00 | Fined\n$225.00     | Outstanding\n$775.00     | Paid\n']]

        response2 = {
          'error_on_lookup'  : False,
          'response_args'    : response_args2,
          'response_parts'   : response_parts2,
          'success'          : True,
          'successful_lookup': True
        }

        plate_lookup_mock.return_value = plate_lookup2

        self.assertEqual(self.aggregator.process_response_message(response_args2), response2)



        #############################
        # Test campaign-only lookup #
        #############################

        username3        = 'NYCMayorsOffice'
        campaign_hashtag = '#SaferSkillman'
        response_args3   = {
          'created_at': utc_time.strftime('%a %b %d %H:%M:%S %z %Y'),
          'id': message_id,
          'legacy_string_parts': ['@howsmydrivingny',
                                  campaign_hashtag],
          'string_parts': ['@howsmydrivingny',
                           campaign_hashtag],
          'type': 'status',
          'username': username3
        }


        campaign_tickets  = random.randint(1000, 2000)
        campaign_vehicles = random.randint(100, 200)

        campaign_result = {
          'included_campaigns': [
            {
              'campaign_hashtag': campaign_hashtag,
              'campaign_tickets': campaign_tickets,
              'campaign_vehicles': campaign_vehicles
            }
          ]
        }

        included_campaigns = [(1, campaign_hashtag)]

        response_parts3 = [['@' + username3 + ' ' + str(campaign_vehicles) + ' vehicles with a total of ' + str(campaign_tickets) + ' tickets have been tagged with ' + campaign_hashtag + '.\n\n']]


        response3 = {
          'error_on_lookup'  : False,
          'response_args'    : response_args3,
          'response_parts'   : response_parts3,
          'success'          : True,
          'successful_lookup': True
        }

        detect_campaign_hashtags_mock = MagicMock(name='detect_campaign_hashtags')
        detect_campaign_hashtags_mock.return_value = included_campaigns

        perform_campaign_lookup_mock = MagicMock(name='perform_campaign_lookup')
        perform_campaign_lookup_mock.return_value = campaign_result

        self.aggregator.detect_campaign_hashtags = detect_campaign_hashtags_mock
        self.aggregator.perform_campaign_lookup  = perform_campaign_lookup_mock

        self.assertEqual(self.aggregator.process_response_message(response_args3), response3)

        perform_campaign_lookup_mock.assert_called_with(included_campaigns)



        #########################
        # Test plateless lookup #
        #########################

        username4        = 'NYC_DOT'
        response_args4   = {
          'created_at': utc_time.strftime('%a %b %d %H:%M:%S %z %Y'),
          'id': message_id,
          'legacy_string_parts': ['@howsmydrivingny',
                                  'plate',
                                  'dkr9364',
                                  'state',
                                  'ny'],
          'string_parts': ['@howsmydrivingny',
                           'plate',
                           'dkr9364',
                           'state',
                           'ny'],
          'type': 'status',
          'username': username4
        }

        response_parts4 = [['@' + username4 + ' I’d be happy to look that up for you!\n\nJust a reminder, the format is <state|province|territory>:<plate>, e.g. NY:abc1234']]

        response4 = {
          'error_on_lookup'  : False,
          'response_args'    : response_args4,
          'response_parts'   : response_parts4,
          'success'          : True,
          'successful_lookup': False
        }

        detect_campaign_hashtags_mock.return_value = []

        self.assertEqual(self.aggregator.process_response_message(response_args4), response4)



        username5        = 'NYCDDC'
        response_args5   = {
          'created_at': utc_time.strftime('%a %b %d %H:%M:%S %z %Y'),
          'id': message_id,
          'legacy_string_parts': ['@howsmydrivingny',
                                  'the',
                                  'state',
                                  'is',
                                  'ny'],
          'string_parts': ['@howsmydrivingny',
                           'the',
                           'state',
                           'is',
                           'ny'],
          'type': 'status',
          'username': username5
        }

        response_parts5 = [['@' + username5 + " I think you're trying to look up a plate, but can't be sure.\n\nJust a reminder, the format is <state|province|territory>:<plate>, e.g. NY:abc1234"]]

        response5 = {
          'error_on_lookup'  : False,
          'response_args'    : response_args5,
          'response_parts'   : response_parts5,
          'success'          : True,
          'successful_lookup': False
        }

        self.assertEqual(self.aggregator.process_response_message(response_args5), response5)



        #######################
        # Test error handling #
        #######################

        response_parts6 = [['@' + username2 + " Sorry, I encountered an error. Tagging @bdhowald."]]

        self.aggregator.perform_plate_lookup = create_error

        self.aggregator.process_response_message(response_args2)

        response6 = {
          'error_on_lookup'  : False,
          'response_args'    : response_args2,
          'response_parts'   : response_parts6,
          'success'          : True,
          'successful_lookup': False
        }

        self.assertEqual(self.aggregator.process_response_message(response_args2), response6)

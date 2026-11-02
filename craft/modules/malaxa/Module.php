<?php

namespace modules\malaxa;

use Craft;
use craft\console\Application as ConsoleApplication;
use yii\base\Module as BaseModule;

/**
 * Site module: console commands for building the content model and importing
 * the hospital's content (see console/controllers).
 */
class Module extends BaseModule
{
    public function init(): void
    {
        Craft::setAlias('@modules/malaxa', __DIR__);

        if (Craft::$app instanceof ConsoleApplication) {
            $this->controllerNamespace = 'modules\\malaxa\\console\\controllers';
        } else {
            $this->controllerNamespace = 'modules\\malaxa\\controllers';
        }

        parent::init();
    }
}
